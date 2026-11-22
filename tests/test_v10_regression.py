"""v1.0: known names must not be blocked solely by uncertain tiny loot icons."""
import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image, ImageDraw
from app import analyse_image
from overlay import overlay_summary
from image_regions import fate_image_regions


def synthetic_three():
    img=Image.new('RGB',(2048,1151),'#121921')
    draw=ImageDraw.Draw(img)
    for i,x in enumerate((660,945,1230)):
        draw.rectangle((x-27,140,x+210,490),fill='#442a23')
        draw.rectangle((x,145,x+180,193),fill=(190,147,93))
        draw.ellipse((x+80,450,x+116,486),fill=('white' if i==0 else 'gold'))
    return img


def mock_result(namestatus='hoch',overall='niedrig'):
    return {'screen_type':'selection','confidence':overall,'names_confidence':namestatus,
            'best_number':0,'recommendation':'','cards':[
                {'number':i,'name':name,'reward_icon':'unknown',
                 'reward_icon_confidence':'niedrig','reward_tooltip':'',
                 'danger':'mittel','notes':'Gefährliche Effekte'}
                for i,name in enumerate(('Stormcaller','Tempest','Black Frost'),1)]}


class NewValidation(unittest.TestCase):
    def evaluate(self,data):
        client=MagicMock()
        client.responses.create.return_value=MagicMock(output_text=json.dumps(data))
        with patch.dict(sys.modules,{'openai':types.SimpleNamespace(OpenAI=lambda **kw:client)}):
            res=analyse_image(synthetic_three(),'not-real','Kampagne','Sicher',[])
        self.assertEqual(client.responses.create.call_count,1)
        return res

    def test_uncertain_loot_still_recognizes_three_names(self):
        res=self.evaluate(mock_result())
        self.assertEqual(res['visual_verification'],'geometry_confirmed')
        self.assertEqual([c['name'] for c in res['cards']],['Stormcaller','Tempest','Black Frost'])
        self.assertEqual(res['confidence'],'mittel')
        self.assertIn(res['best_number'],(1,2,3))
        self.assertTrue(all(c['rewards']=='Loot-Symbol nicht sicher erkannt' for c in res['cards']))

    def test_uncertain_names_are_not_highlighted(self):
        res=self.evaluate(mock_result(namestatus='niedrig'))
        self.assertEqual(res['best_number'],0)
        self.assertEqual(res['visual_verification'],'mismatch')
        summary=overlay_summary(res)
        self.assertIn('Grund:',summary['sub'])
        self.assertFalse(summary['can_save'])

    def test_known_name_spacing_is_normalized(self):
        d=mock_result();d['cards'][2]['name']='Black-Frost'
        res=self.evaluate(d)
        self.assertEqual(res['cards'][2]['name'],'Black Frost')

    def test_old_global_low_without_name_confidence_is_conservative(self):
        d=mock_result();d.pop('names_confidence')
        res=self.evaluate(d)
        self.assertEqual(res['best_number'],0)

    def test_local_shape_detects_three_cards(self):
        view=fate_image_regions(synthetic_three())
        self.assertEqual(view.cards_count,3)
        self.assertTrue(view.geometry_confident)

    def test_version_label_is_not_old(self):
        from pathlib import Path
        text=(Path(__file__).resolve().parents[1]/'overlay.py').read_text(encoding='utf8')
        self.assertIn('FATE ADVISOR v"+VERSION',text)
        self.assertIn('from app_updates import VERSION',text)
        self.assertNotIn('FATE ADVISOR v0.8',text)

if __name__=='__main__': unittest.main()
