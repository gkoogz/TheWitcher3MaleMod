from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import ordered_worker_adoption as adoption


class OwnershipAdoptionTest(unittest.TestCase):
    def test_changed_ownership_uses_independent_api_and_explicit_legacy_reference(self):
        commands = adoption.regression_commands(Path('renderer'), Path('worker'),
                                                Path('native'), Path('old.exe'), True)
        mechanical = commands['numerical-and-donor-parity']
        self.assertEqual(mechanical[1], mechanical[2])
        self.assertEqual(commands['worker-api'][-1], '--target-owned')
        self.assertEqual(commands['minimum-target-owned-api'][-2:], ['--target-owned', '--minimum'])
        self.assertEqual(commands['minimum-legacy-reference-api'][1:],
                         [Path('old.exe'), '--legacy', '--minimum'])

    def test_legacy_adoption_retains_old_worker_parity(self):
        commands = adoption.regression_commands(Path('renderer'), Path('worker'),
                                                Path('native'), Path('old.exe'))
        self.assertEqual(commands['numerical-and-donor-parity'][2], Path('old.exe'))
        self.assertEqual(len(commands), 3)

    def test_target_mode_requires_bound_configuration_and_all_regressions(self):
        with tempfile.TemporaryDirectory() as temp:
            build = Path(temp)
            cache = build/'CMakeCache.txt'
            cache.write_text('MALEMOD_WORKER_TARGET_OWNS_COLLAR:BOOL=ON\n')
            proof = dict(schema='malemod.ordered-worker-adoption/2', workerBuild=str(build),
                         collarOwnership='target', referenceCollarOwnership='legacy',
                         referenceParityClaimed=False,
                         evidence=[dict(path=str(cache), sha256=adoption.digest(cache))],
                         tests={name: dict(exitCode=0) for name in adoption.regression_commands(
                             build, build, build, build/'old.exe', True)})
            self.assertTrue(adoption.validate_regressions(proof))
            proof['referenceParityClaimed'] = True
            with self.assertRaisesRegex(ValueError, 'explicitly identified'):
                adoption.validate_regressions(proof)
            proof['referenceParityClaimed'] = False
            saved = proof['tests'].pop('minimum-target-owned-api')
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                adoption.validate_regressions(proof)
            proof['tests']['minimum-target-owned-api'] = saved
            cache.write_text('MALEMOD_WORKER_TARGET_OWNS_COLLAR:BOOL=OFF\n')
            with self.assertRaisesRegex(ValueError, 'not bound'):
                adoption.validate_regressions(proof)
            proof['evidence'][0]['sha256'] = adoption.digest(cache)
            with self.assertRaisesRegex(ValueError, 'requested attachment mode'):
                adoption.validate_regressions(proof)


if __name__ == '__main__':
    unittest.main()
