"""Regression for user's repeated 'Keine sichere neue Coven-Auswahl erkannt'."""
import json,sys,types,unittest
from unittest.mock import MagicMock,patch
from PIL import Image,ImageDraw
from app import analyse_image


def screen_with_three():
    im=Image.new('RGB',(2048,1151),'#10151a')
    d=ImageDraw.Draw(im)
    for x in (660,945,1230):
        d.rectangle((x-15,320,x+175,685),fill='#4b3026')
        d.rectangle((x,327,x+160,374),fill=(191,154,108))
        d.ellipse((x+70,630,x+110,675),fill=(86,122,160))
    return im


def cards(names=('Stormcaller','Tempest','Black Frost')):
    return [{'number':i,'name':n,'reward_icon':'unknown',
             'reward_icon_confidence':'niedrig','danger':'mittel',
             'notes':'Angriffen ausweichen'} for i,n in enumerate(names,1)]


def analyze_with_payload(payload):
    client=MagicMock()
    client.responses.create.return_value=MagicMock(output_text=json.dumps(payload))
    with patch.dict(sys.modules,{'openai':types.SimpleNamespace(OpenAI=lambda **kwargs:client)}):
        answer=analyse_image(screen_with_three(),'test-only','Kampagne','Sicher',[])
    return answer,client


class V11Regression(unittest.TestCase):
    def test_model_says_unknown_but_visible_cards_are_read(self):
        result,client=analyze_with_payload({
            'screen_type':'unknown','confidence':'niedrig',
            'names_confidence':'hoch','cards':cards()})
        self.assertEqual([c['name'] for c in result['cards']],
                         ['Stormcaller','Tempest','Black Frost'])
        self.assertEqual(result['visual_verification'],'geometry_confirmed')
        self.assertIn(result['best_number'],(1,2,3))
        self.assertEqual(client.responses.create.call_count,1)
        kwargs=client.responses.create.call_args.kwargs
        self.assertEqual(kwargs['text']['format']['type'],'json_schema')
        self.assertTrue(kwargs['text']['format']['strict'])
        self.assertIn('EXACTLY 3', kwargs['input'][0]['content'][0]['text'])

    def test_model_returns_only_new_simple_schema(self):
        result,_=analyze_with_payload({'names_confidence':'hoch','cards':cards()})
        self.assertEqual(result['screen_type'],'selection')
        self.assertGreater(result['best_number'],0)
        self.assertEqual(result['confidence'],'mittel')  # loot unclear only

    def test_known_but_extra_card_is_rejected(self):
        result,_=analyze_with_payload({'names_confidence':'hoch',
                     'cards':cards(('Stormcaller','Tempest','Black Frost','Crowkeeper'))})
        self.assertEqual(result['best_number'],0)
        self.assertEqual(result['visual_verification'],'mismatch')

    def test_empty_model_result_does_not_trigger_false_mark(self):
        result,_=analyze_with_payload({'names_confidence':'niedrig','cards':[]})
        self.assertEqual(result['best_number'],0)
        self.assertEqual(result['visual_verification'],'mismatch')
        self.assertIn('keine Kartennamen',result['uncertainty'])

if __name__=='__main__':unittest.main()
