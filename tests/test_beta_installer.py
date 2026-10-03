"""Run the shipped PowerShell workflow in isolated, complete package fixtures."""
import hashlib,json,re,shutil,subprocess,sys,unittest,uuid,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_beta_release import digest
PACKAGE=ROOT/'publish/Witcher3MaleMod-0.5.0-beta.1-Install'
class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (PACKAGE.parent/(PACKAGE.name+'.zip')).is_file():raise unittest.SkipTest('Build the beta install ZIP first')
        cls.root=ROOT/'build'/('ri-'+uuid.uuid4().hex[:8])
        cls.root.mkdir(parents=True)
        cls.shipped=cls.root/'pkg'
        with zipfile.ZipFile(PACKAGE.parent/(PACKAGE.name+'.zip')) as z:z.extractall(cls.shipped)
        m=json.loads((cls.shipped/'manifest.json').read_text())
        for row in m['packageFiles']:
            if digest(cls.shipped/row['path'])!=row['sha256']:raise AssertionError('Shipped installer hash differs')
            if (cls.shipped/row['path']).read_bytes()!=(ROOT/'release'/row['path']).read_bytes():raise AssertionError('Shipped installer source differs')
    def setUp(self):
        self.case=self.root/('c'+str(sorted(n for n in dir(self) if n.startswith('test_')).index(self._testMethodName)));self.case.mkdir()
        self.game=self.case/'Game';(self.game/'bin/x64_dx12').mkdir(parents=True)
        (self.game/'bin/x64_dx12/witcher3.exe').write_bytes(b'fixture-only-no-game-launch')
        self.package=self.shipped
        self.settings=self.game/'bin/x64_dx12/malemod-native/preferences.json';self.settings.parent.mkdir(parents=True)
        self.settings.write_bytes(b'private preferences preserve exactly')
        self.user=self.game/'user.settings';self.user.write_bytes(b'untouched user settings')
    def run_action(self,action,backup=None,ok=True):
        cmd=['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(self.package/'Manage.ps1'),'-Action',action,'-GamePath',str(self.game)]
        if backup:cmd+=['-BackupId',backup]
        p=subprocess.run(cmd,capture_output=True,text=True)
        if ok:self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        else:self.assertNotEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertEqual(self.settings.read_bytes(),b'private preferences preserve exactly');self.assertEqual(self.user.read_bytes(),b'untouched user settings')
        m=re.search(r'Rollback ID: ([0-9a-f]{32})',p.stdout);return m.group(1) if m else p
    def manifest(self):return json.loads((self.package/'manifest.json').read_text())
    def verify_installed(self,rows=None):
        for row in rows or self.manifest()['files']:self.assertEqual(digest(self.game/row['path']),row['sha256'],row['path'])
    def verify_absent(self):
        for row in self.manifest()['files']:self.assertFalse((self.game/row['path']).exists(),row['path'])
    def clone_package(self):
        self.package=self.case/'package';shutil.copytree(self.shipped,self.package)
        # Refresh copied tools from versioned source so development iterations remain exact.
        for p in (ROOT/'release').iterdir():
            if p.is_file():shutil.copy2(p,self.package/p.name)
        self.refresh_manifest()
    def refresh_manifest(self):
        m=self.manifest()
        for row in m['packageFiles']:row['sha256']=digest(self.package/row['path'])
        (self.package/'manifest.json').write_text(json.dumps(m))
    def test_clean_idempotent_uninstall_exact_rollback(self):
        self.run_action('Install');self.verify_installed()
        self.run_action('Install');self.verify_installed()
        backup=self.run_action('Uninstall');self.verify_absent()
        self.run_action('Rollback',backup);self.verify_installed()
    def test_clean_install_rollback_to_absence(self):
        backup=self.run_action('Install');self.run_action('Rollback',backup);self.verify_absent()
    def test_supported_manual_adoption_upgrade(self):
        for row in self.manifest()['files']:
            target=self.game/row['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(self.package/'payload'/row['path'],target)
        self.run_action('Upgrade');self.verify_installed()
    def test_baseline_only_upgrade_and_rollback(self):
        rows=self.manifest()['supportedManualInstalls'][0]['files']
        for row in rows:
            target=self.game/row['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(self.package/'payload'/row['path'],target)
        backup=self.run_action('Upgrade');self.verify_installed();self.run_action('Rollback',backup);self.verify_installed(rows)
        for row in self.manifest()['files'][:25]:self.assertFalse((self.game/row['path']).exists())
    def test_previous_accepted_snapshot_upgrade_rollback(self):
        previous=ROOT/'local/native-backup-20261002-230911'
        if not (previous/'receipt.json').is_file():self.skipTest('Historical accepted snapshot is local-only')
        m=json.loads((previous/'receipt.json').read_text())
        rows=m['files']+self.manifest()['files'][25:]
        for row in rows:
            source=previous/row['path'] if row['path'] in {r['path'] for r in m['files']} else self.package/'payload'/row['path']
            self.assertEqual(digest(source),row['sha256'])
            target=self.game/row['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        backup=self.run_action('Upgrade');self.verify_installed();self.run_action('Rollback',backup);self.verify_installed(rows)
        old={r['path'] for r in rows}
        for row in self.manifest()['files']:
            if row['path'] not in old:self.assertFalse((self.game/row['path']).exists())
    def test_junction_rejected_without_touching_outside(self):
        outside=self.case/'outside';outside.mkdir();marker=outside/'marker';marker.write_bytes(b'outside preserved')
        junction=self.game/'Mods'
        command="New-Item -ItemType Junction -Path '%s' -Target '%s' | Out-Null"%(str(junction).replace("'","''"),str(outside).replace("'","''"))
        p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.run_action('Install',ok=False);self.assertEqual(marker.read_bytes(),b'outside preserved');self.assertEqual(len(list(outside.iterdir())),1)
    def test_unknown_proxy_rejected(self):
        proxy=self.game/'bin/x64_dx12/dinput8.dll';proxy.write_bytes(b'other mod proxy')
        self.run_action('Install',ok=False);self.assertEqual(proxy.read_bytes(),b'other mod proxy')
        self.assertFalse((self.game/'.malemod-installation').exists())
    def test_modified_managed_rejected(self):
        self.run_action('Install');proxy=self.game/'bin/x64_dx12/dinput8.dll';proxy.write_bytes(b'user changed proxy')
        self.run_action('Upgrade',ok=False);self.run_action('Uninstall',ok=False);self.assertEqual(proxy.read_bytes(),b'user changed proxy')
    def test_missing_managed_rejected(self):
        self.run_action('Install');(self.game/'bin/x64_dx12/dinput8.dll').unlink();self.run_action('Install',ok=False)
    def test_tampered_payload_rejected_before_game_mutation(self):
        self.clone_package();(self.package/'payload/bin/x64_dx12/dinput8.dll').write_bytes(b'tampered')
        self.run_action('Install',ok=False);self.verify_absent()
    def test_path_escape_rejected(self):
        self.clone_package();m=self.manifest();m['files'][0]['path']='../outside.bin';(self.package/'manifest.json').write_text(json.dumps(m))
        self.run_action('Install',ok=False);self.assertFalse((self.case/'outside.bin').exists())
    def test_transaction_restores_receipt_and_files(self):
        self.run_action('Install');receipt=self.game/'.malemod-installation/current.json';before=receipt.read_bytes()
        self.clone_package();script=self.package/'Manage.ps1';s=script.read_text(encoding='utf-8-sig')
        needle='CopyVerified (Child $sourceRoot $row.path) (Child $game $row.path) $row.sha256 }'
        self.assertIn(needle,s);s=s.replace(needle,'CopyVerified (Child $sourceRoot $row.path) (Child $game $row.path) $row.sha256; throw "Fixture injected write failure" }',1)
        script.write_text(s);self.refresh_manifest()
        self.run_action('Upgrade',ok=False);self.verify_installed();self.assertEqual(receipt.read_bytes(),before)
    def test_rollback_backup_tamper_rejected(self):
        backup=self.run_action('Install');self.run_action('Install')
        self.run_action('Rollback',backup='../../outside',ok=False);self.verify_installed()
    def test_receipt_unmanaged_path_rejected(self):
        self.run_action('Install');receipt=self.game/'.malemod-installation/current.json';m=json.loads(receipt.read_text(encoding='utf-8-sig'))
        outside=self.game/'innocent.txt';outside.write_bytes(b'do not remove');m['files'].append(dict(path='innocent.txt',sha256=digest(outside)));receipt.write_text(json.dumps(m))
        self.run_action('Uninstall',ok=False);self.assertEqual(outside.read_bytes(),b'do not remove')
if __name__=='__main__':unittest.main()
