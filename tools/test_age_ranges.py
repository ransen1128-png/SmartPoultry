"""Synthetic protocol checks only; these tests make no model accuracy claim."""
import unittest
from calibrate_age_ranges import calibrate


class CalibrationProtocolTests(unittest.TestCase):
    def report(self):
        return {'independent_evaluation_executed':True,'provenance_sha256':'synthetic-fixture',
            'checkpoint_sha256':'fixture-model','predictions':[{'chicken_id':str(i),'age_months':12,
                'prediction_months':12+(i%4)*.5} for i in range(50)]}

    def test_requires_verified_provenance_and_enough_chickens(self):
        report=self.report();report['independent_evaluation_executed']=False
        with self.assertRaises(ValueError):calibrate(report)
        report=self.report();report['predictions']=report['predictions'][:39]
        with self.assertRaises(ValueError):calibrate(report)

    def test_disjoint_reproducible_bird_splits(self):
        first=calibrate(self.report());second=calibrate(self.report())
        self.assertEqual(first,second)
        self.assertFalse(set(first['calibration_ids'])&set(first['test_ids']))
        self.assertEqual(first['calibration_chickens'],25)

    def test_test_errors_do_not_choose_range_width(self):
        report=self.report();initial=calibrate(report);test=set(initial['test_ids'])
        for row in report['predictions']:
            if row['chicken_id'] in test:row['prediction_months']=24
        changed=calibrate(report)
        self.assertEqual(initial['radius_months'],changed['radius_months'])
        self.assertLess(changed['held_out_bird_coverage'],initial['held_out_bird_coverage'])


if __name__=='__main__':unittest.main()
