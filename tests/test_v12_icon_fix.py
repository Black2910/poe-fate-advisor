"""Regression for mislabeled Dryad rare Wand as Currency in user's screenshot."""
import json,sys,types,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from PIL import Image,ImageDraw
from image_regions import fate_image_regions
from icon_reference import BASE,match_icon,independently_read_icons
from app import analyse_image


def synthetic_current_choice():
    im=Image.new('RGB',(2048,1151),'#122023')
    d=ImageDraw.Draw(im)
    for x in (660,945,1230):
        d.rectangle((x-15,115,x+175,488),fill='#53372e')
        d.rectangle((x,120,x+160,165),fill=(191,154,108))
    # The verified in-game sprites are from actual user screenshots; each is
    # a randomized reward, NOT a Fate-dependent lookup.
    im.paste(Image.open(BASE/'Wand_01.png'),(741-33,470-33))
    im.paste(Image.open(BASE/'Axe_01.png'),(1310-33,470-33))
    return im


class IconFixTests(unittest.TestCase):
    def test_known_wand_is_not_currency(self):
        with Image.open(BASE/'Wand_01.png') as image:
            hit=match_icon(image)
        self.assertEqual(hit.category,'Wand')
        self.assertGreater(hit.similarity,.9)

    def test_known_currency_is_currency(self):
        with Image.open(BASE/'Currency_01.png') as image:
            hit=match_icon(image)
        self.assertEqual(hit.category,'Currency')

    def test_local_recheck_overrules_model_hallucination(self):
        # The fake AI intentionally hallucinates a Currency reward on Dryad.
        # The new structured schema doesn't request icons at all.
        payload={'names_confidence':'hoch','cards':[
            {'number':1,'name':'Dryad','danger':'mittel','notes':'vines',
             'reward_icon':'Currency','reward_icon_confidence':'hoch'},
            {'number':2,'name':'Tempest','danger':'mittel','notes':'orbs'},
            {'number':3,'name':'Torchbearer','danger':'mittel','notes':'fire'},
        ]}
        client=MagicMock()
        client.responses.create.return_value=MagicMock(output_text=json.dumps(payload))
        fake_openai=types.SimpleNamespace(OpenAI=lambda **kwargs:client)
        with patch.dict(sys.modules,{'openai':fake_openai}):
            result=analyse_image(synthetic_current_choice(),'not-a-key','Kampagne','Ausgewogen',[])
        self.assertEqual(client.responses.create.call_count,1)
        # Strict schema no longer contains the reward_icon request.
        schema=client.responses.create.call_args.kwargs['text']['format']['schema']
        self.assertNotIn('reward_icon',schema['properties']['cards']['items']['properties'])
        self.assertEqual(result['cards'][0]['reward_icon'],'Wand')
        self.assertNotIn('Währungsgegenstände',result['cards'][0]['rewards'])
        self.assertEqual(result['cards'][1]['reward_icon'],'unknown')

if __name__=='__main__':unittest.main()
