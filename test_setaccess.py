import unittest
from unittest import TestCase

import setaccess


class TestRequestPermissions(unittest.TestCase):
    def test_get_acls(self):
        # (self, lab, members, request, request_name, request_members, groups, fastqs, isDLP):
        p = setaccess.RequestPermissions("labX",
                                         [{"pi": "kunga","member": "kunga","group": False}],
                                         "08822", "DLP",
                                         [{'request': '08822', 'member': 'mcmanamd', 'group': False}],
                                         ["cmoigo", "bicigo"],
                                         [" vialea"],  # dataAccessEmails
                                         ["none"],
                                         [True])

        print("ACL access list:\n" + p.get_acls())
        self.assertIn("A:g:bicigo@hpc.private:rxtncy", p.get_acls())
        self.assertIn("A::kunga@hpc.private:rxtncy", p.get_acls())
        self.assertIn("A::mcmanamd@hpc.private:rxtncy", p.get_acls())
        self.assertIn("A::vialea@hpc.private:rxtncy", p.get_acls())
        self.assertIn("A::grewald@hpc.private:rxtncy", p.get_acls())
        self.assertIn("A::GROUP@:rxtncCy", p.get_acls())


class Test(TestCase):
    def test_get_request_metadata(self):
        p = setaccess.get_request_metadata("08822", "none")
        print("Lab members for 08822 {}".format(p.members))
        print("Lab request members for 08822 {}".format(p.request_members))
        self.assertEqual("shuklan", p.lab)

    def test_get_request_metadata_invalid_request(self):
        p = setaccess.get_request_metadata("08822_XXX", "none")
        print("No information found from endpoint for: {}".format(p))
        self.assertIsNone(p)