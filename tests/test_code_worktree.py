import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('code_worktree', Path(__file__).parents[1]/'bin/code_worktree.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CodeWorktreeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bfa worktrees ')
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.origin = root/'upstream'
        self.origin.mkdir()
        self.env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
        self.env.update(HOME=str(root),GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='url.'+self.origin.as_uri()+'.insteadOf',GIT_CONFIG_VALUE_0='https://github.com/example/repo.git')
        self.git('init','--initial-branch=master',str(self.origin))
        self.git('-C',str(self.origin),'config','user.name','Fixture')
        self.git('-C',str(self.origin),'config','user.email','fixture@example.invalid')
        (self.origin/'file.txt').write_text('master version\n')
        self.commit('initial')
        self.git('-C',str(self.origin),'checkout','-b','feature/a')
        (self.origin/'file.txt').write_text('feature version\n')
        self.commit('feature')
        self.git('-C',str(self.origin),'checkout','master')
        self.registry=module.repositories(json.dumps({'example':{'url':'https://github.com/example/repo.git','branch':'master'}}))
        self.manager=module.Worktrees(root/'sources',self.registry,lambda args:self.run_git(*args))

    def run_git(self,*args):
        return subprocess.run(['git',*args],env=self.env,capture_output=True,text=True)

    def git(self,*args):
        r=self.run_git(*args)
        self.assertEqual(r.returncode,0,r.stderr)
        return r.stdout.strip()

    def commit(self,name):
        self.git('-C',str(self.origin),'add','file.txt')
        self.git('-C',str(self.origin),'commit','-m',name)

    def test_two_branches_coexist_and_do_not_switch_existing_checkout(self):
        main=self.manager.open('example')
        feature=self.manager.open('example','feature/a')
        self.assertNotEqual(main['path'],feature['path'])
        self.assertEqual((Path(main['path'])/'file.txt').read_text(),'master version\n')
        self.assertEqual((Path(feature['path'])/'file.txt').read_text(),'feature version\n')
        self.assertEqual(self.git('-C',main['path'],'rev-parse','HEAD'),main['sha'])
        self.assertEqual(len(self.manager.entries()),2)
        index=(self.manager.root/'WORKTREES.md').read_text()
        self.assertIn(main['path'],index)
        self.assertIn(feature['path'],index)

    def test_same_version_reuses_clean_worktree(self):
        first=self.manager.open('example')
        again=self.manager.open('example')
        self.assertEqual(first['path'],again['path'])
        self.assertEqual(len(self.manager.entries()),1)

    def test_remote_update_reuses_directory_and_updates_content(self):
        first=self.manager.open('example')
        (self.origin/'file.txt').write_text('updated\n')
        self.commit('update')
        second=self.manager.open('example')
        self.assertNotEqual(first['sha'],second['sha'])
        self.assertEqual(first['path'],second['path'])
        self.assertEqual(len(self.manager.entries()),1)
        self.assertEqual((Path(second['path'])/'file.txt').read_text(),'updated\n')

    def test_managed_local_changes_and_untracked_files_are_discarded(self):
        first=self.manager.open('example')
        f=Path(first['path'])/'file.txt';f.write_text('local analysis changes\n')
        scratch=Path(first['path'])/'scratch.txt';scratch.write_text('temporary')
        self.manager.open('example')
        self.assertEqual(f.read_text(),'master version\n')
        self.assertFalse(scratch.exists())

    def test_force_pushed_branch_replaces_local_cached_version(self):
        first=self.manager.open('example')
        self.git('-C',str(self.origin),'checkout','--orphan','replacement')
        (self.origin/'file.txt').write_text('rewritten history\n')
        self.commit('replacement')
        self.git('-C',str(self.origin),'branch','-f','master','HEAD')
        second=self.manager.open('example')
        self.assertEqual(first['path'],second['path'])
        self.assertNotEqual(first['sha'],second['sha'])
        self.assertEqual((Path(second['path'])/'file.txt').read_text(),'rewritten history\n')

    def test_missing_remote_branch_does_not_return_old_snapshot(self):
        self.manager.open('example')
        with self.assertRaises(RuntimeError):self.manager.open('example','missing')
        self.assertEqual(len(self.manager.entries()),1)

    def test_path_traversal_and_options_are_rejected(self):
        with self.assertRaises(ValueError):self.manager.open('../other')
        with self.assertRaises(ValueError):self.manager.open('example','--upload-pack=bad')
        with self.assertRaises(RuntimeError):self.manager.open('example','../../bad')

    def test_branch_slugs_that_look_the_same_have_distinct_directories(self):
        self.git('-C',str(self.origin),'branch','feature-a','master')
        a=self.manager.open('example','feature/a')
        b=self.manager.open('example','feature-a')
        self.assertNotEqual(a['path'],b['path'])

    def test_registry_rejects_credential_urls_and_unexpected_hosts(self):
        for url in ['https://token@github.com/example/repo.git','http://github.com/example/repo.git','https://example.invalid/example/repo.git']:
            with self.subTest(url=url),self.assertRaises(ValueError):
                module.repositories(json.dumps({'example':{'url':url,'branch':'master'}}))

    def test_remove_cleans_only_selected_registered_worktree_and_index(self):
        main=self.manager.open('example')
        feature=self.manager.open('example','feature/a')
        self.manager.remove('example','feature/a')
        self.assertFalse(Path(feature['path']).exists())
        self.assertTrue(Path(main['path']).is_dir())
        self.assertEqual(len(self.manager.entries()),1)
        self.assertNotIn(feature['path'],(self.manager.root/'WORKTREES.md').read_text())

    def test_remove_refuses_dirty_worktree(self):
        entry=self.manager.open('example')
        f=Path(entry['path'])/'scratch.txt';f.write_text('preserve until next explicit sync')
        with self.assertRaises(RuntimeError):self.manager.remove('example','master')
        self.assertTrue(f.exists())


if __name__ == '__main__':
    unittest.main()
