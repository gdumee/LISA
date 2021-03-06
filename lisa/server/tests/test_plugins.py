from lisa.server.plugins.PluginManager import PluginManager
from twisted.trial import unittest
import os
import json

class LisaPluginTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_a_install_plugin_ok(self):
        answer = PluginManager.installPlugin(plugin_name="UnitTest", test_mode=True)
        self.assertEqual(answer['status'], "success")

    def test_aa_install_plugin_fail(self):
        answer = PluginManager.installPlugin(plugin_name="UnitTest", test_mode=True)
        self.assertEqual(answer['status'], "fail")

    def test_b_disable_plugin_ok(self):
        answer = PluginManager.disablePlugin(plugin_name="UnitTest")
        self.assertEqual(answer['status'], "success")

    def test_bb_disable_plugin_fail(self):
        answer = PluginManager.disablePlugin(plugin_name="UnitTest")
        self.assertEqual(answer['status'], "fail")

    def test_c_enable_plugin_ok(self):
        answer = PluginManager.enablePlugin(plugin_name="UnitTest")
        self.assertEqual(answer['status'], "success")

    def test_cc_enable_plugin_fail(self):
        answer = PluginManager.enablePlugin(plugin_name="UnitTest")
        self.assertEqual(answer['status'], "fail")

    def test_d_load_plugin(self):
        answer = PluginManager.getEnabledPluginNames()
        test_list = ['UnitTest']
        self.assertListEqual(answer, test_list)

    def test_e_methodList_plugin(self):
        answer = PluginManager.getPluginMethods()
        methodlist = [{'methods': ['test'], 'plugin': u'UnitTest'}, {'core': 'intents', 'methods': ['list']}]
        self.assertListEqual(answer, methodlist)

    def test_f_create_plugin(self):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lisa.server.web.weblisa.settings")
        answer = PluginManager.createPlugin(plugin_name="TestPlugin", author_name="TestAuthor",
                                                 author_email="test@test.com")
        self.assertEqual(answer['status'], "success")

    def test_g_uninstall_plugin(self):
        answer = PluginManager.uninstallPlugin(plugin_name="UnitTest")
        self.assertEqual(answer['status'], "success")

    def test_gg_uninstall_plugin(self):
        answer = PluginManager.uninstallPlugin(plugin_name="UnitTest")
        self.assertEqual(answer['status'], "fail")
