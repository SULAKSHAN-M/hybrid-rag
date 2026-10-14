import os
import unittest
from unittest.mock import patch
from app.llm import GEMINI_MODELS, GenerationError, generate_auto, route, settings

class RouterTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GEMINI_API_KEY': 'test-placeholder'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_task_routing(self):
        for question, sources, expected in [
            ('How many remote days?', [], 'gemini-3.5-flash-lite'),
            ('Compare these policies', [], 'gemini-3.1-pro-preview'),
            ('Explain the policy', [], 'gemini-3.6-flash'),
            ('Debug this Python code', [], 'gemini-3.7-flash'),
            ('What does it say?', [{'text':'a'*19000}], 'gemini-3.8-flash')]:
            order, _ = route(question, sources, GEMINI_MODELS)
            self.assertEqual(order[0], expected)
            self.assertEqual(set(order), set(GEMINI_MODELS))

    def test_success_makes_one_call(self):
        with patch('app.llm.generate', return_value={'claims':[]}) as call:
            _, info = generate_auto('s', 'Question?', [])
            self.assertEqual(call.call_count, 1)
            self.assertFalse(info['fallback_used'])

    def test_unavailable_model_falls_back(self):
        with patch('app.llm.generate', side_effect=[GenerationError('Unavailable', True), {'claims':[]}]) as call:
            _, info = generate_auto('s', 'Question?', [])
            self.assertTrue(info['fallback_used'])
            self.assertEqual(len(info['attempted_models']), 2)
            self.assertEqual(info['model'], call.call_args.args[3])

    def test_quota_or_permission_error_stops(self):
        with patch('app.llm.generate', side_effect=GenerationError('Quota')) as call:
            with self.assertRaises(GenerationError):
                generate_auto('s', 'q', [])
            self.assertEqual(call.call_count, 1)

    def test_exhaustion_is_bounded(self):
        with patch('app.llm.generate', side_effect=GenerationError('Unavailable', True)) as call:
            with self.assertRaisesRegex(GenerationError, 'Automatic selection'):
                generate_auto('s', 'q', [])
            self.assertEqual(call.call_count, 5)

    def test_legacy_env_does_not_reduce_pool(self):
        os.environ.update(GEMINI_MODEL='old', GEMINI_MODELS='old,older')
        self.assertEqual(len(settings()['models']), 5)

    def test_unsupported_question_language_still_routes(self):
        self.assertEqual(len(route('விடுப்பு எத்தனை நாட்கள்?', [], GEMINI_MODELS)[0]), 5)
