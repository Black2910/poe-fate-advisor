"""One screenshot, one API request; collected Fates cannot become offers."""
import base64, io, json, sys, types, unittest
from unittest.mock import patch, MagicMock
from PIL import Image, ImageDraw
from app import analyse_image
from fate_engine import Fate
from image_regions import fate_image_regions
from vision_sheet import create_visual_sheet


def fake_game(rows=('Conjurer','Incandescent'), lower=True, shifted=False):
    im=Image.new('RGB',(2048,1151),'#121921');d=ImageDraw.Draw(im)
    y=324 if shifted else 145
    # approximate title parchment plate + whole card + visible icon at bottom
    xs={1:[945],2:[810,1085],3:[660,945,1230]}[len(rows)]
    for i,x in enumerate(xs):
        d.rectangle((x-27,y-5,x+210,y+350), fill='#442a23')
        d.rectangle((x,y,x+180,y+48), fill=(190,147,93))
        d.ellipse((x+78,y+305,x+111,y+338),fill=('blue' if i==0 else 'gold'))
    if lower:
        d.rectangle((950,820,1160,995), fill=(255,0,0))
    return im


def mock_card_result(names=('Conjurer','Incandescent'),icons=('RareArmour','Currency')):
    return {'screen_type':'selection','confidence':'hoch','best_number':0,
            'recommendation':'Nimm Crowkeeper von unten!','cards':[
                {'number':i,'name':n,'reward_icon':icons[i-1],
                 'reward_icon_confidence':'hoch','danger':'mittel','reward_tooltip':'',
                 'notes':'Bewegung hilft'}
                for i,n in enumerate(names,1)]}


class TopRowTests(unittest.TestCase):
    def test_layout_dynamic_three_and_two(self):
        for count,y in ((3,False),(2,True),(2,False)):
            im=fake_game(tuple(['Doomsayer','Conjurer','Incandescent'][:count]),shifted=y)
            v=fate_image_regions(im)
            self.assertEqual(v.cards_count,count)
            self.assertTrue(v.geometry_confident)
            self.assertLess(v.offered_bounds[3],810)
            self.assertFalse(any(r>220 and g<50 and b<50 for r,g,b in v.offered.convert('RGB').getdata()))

    def test_single_api_request_no_history_or_hover_required(self):
        game=fake_game()
        one=MagicMock();one.responses.create.return_value=MagicMock(
            output_text=json.dumps(mock_card_result()))
        with patch.dict(sys.modules,{'openai':types.SimpleNamespace(OpenAI=lambda **kw: one)}):
            result=analyse_image(game,'key','Kampagne','Loot',[Fate('Crowkeeper','Currency')])
        self.assertEqual(one.responses.create.call_count,1)
        self.assertEqual([x['name'] for x in result['cards']],['Conjurer','Incandescent'])
        self.assertNotIn('Crowkeeper',result['recommendation'])
        self.assertEqual(result['visual_verification'],'geometry_confirmed')
        self.assertGreater(result['best_number'],0)
        parts=one.responses.create.call_args.kwargs['input'][0]['content']
        self.assertEqual(sum(i['type']=='input_image' for i in parts),1)
        sh=Image.open(io.BytesIO(base64.b64decode(next(i['image_url'] for i in parts if i['type']=='input_image').split(',')[1])))
        self.assertGreater(sh.width,400)
        self.assertFalse(any(r>220 and g<50 and b<50 for r,g,b in sh.getdata()))
        self.assertNotIn('Crowkeeper',str(one.responses.create.call_args))

    def test_fake_third_option_refused_even_when_model_proposes(self):
        one=MagicMock();one.responses.create.return_value=MagicMock(
          output_text=json.dumps(mock_card_result(('Conjurer','Incandescent','Crowkeeper'),('RareArmour','Currency','Currency'))))
        with patch.dict(sys.modules,{'openai':types.SimpleNamespace(OpenAI=lambda **kw: one)}):
            result=analyse_image(fake_game(),'key','Kampagne','Loot',[])
        self.assertEqual(one.responses.create.call_count,1)
        self.assertEqual(result['best_number'],0)
        self.assertEqual(result['visual_verification'],'mismatch')

    def test_icon_only_is_usable(self):
        result=mock_card_result()
        one=MagicMock();one.responses.create.return_value=MagicMock(output_text=json.dumps(result))
        with patch.dict(sys.modules,{'openai':types.SimpleNamespace(OpenAI=lambda **kw: one)}):
            answer=analyse_image(fake_game(),'key','Kampagne','Loot',[])
        self.assertEqual(answer['cards'][1]['loot_evidence'],'unknown')
        self.assertNotIn('Währungsgegenstände',answer['cards'][1]['rewards'])
        self.assertNotIn('Tooltip prüfen',answer['recommendation'])
        self.assertEqual(answer['cards'][0]['reward_tooltip'],'')

    def test_invocation_no_recommendation(self):
        data={'screen_type':'invocation','confidence':'hoch','best_number':2,'cards':[],
              'invocation_state':'other'}
        one=MagicMock();one.responses.create.return_value=MagicMock(output_text=json.dumps(data))
        with patch.dict(sys.modules,{'openai':types.SimpleNamespace(OpenAI=lambda **kw: one)}):
            answer=analyse_image(fake_game(),'key','Kampagne','Loot',[])
        self.assertEqual(one.responses.create.call_count,1)
        self.assertEqual(answer['best_number'],0)
        self.assertEqual(answer['selected_numbers'],[])

if __name__=='__main__':unittest.main()
