import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from app.llm import GEMINI_MODELS, GenerationError, generate, settings


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GEMINI_API_KEY': 'unit-test-placeholder'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def response(self, payload):
        return io.BytesIO(json.dumps(payload).encode())

    def test_all_five_models_and_private_key_header(self):
        for model in GEMINI_MODELS:
            response = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{"claims":[]}'}]}}]}
            with patch('app.llm.urlopen', return_value=self.response(response)) as call:
                self.assertEqual(generate('System', 'Question', [], model), {'claims': []})
                request = call.call_args.args[0]
                self.assertTrue(request.full_url.endswith(f'/{model}:generateContent'))
                self.assertNotIn('unit-test-placeholder', request.full_url)
                self.assertEqual(request.get_header('X-goog-api-key'), 'unit-test-placeholder')
                body = json.loads(request.data)
                self.assertIn('schema', body['generationConfig']['responseFormat']['text'])

    def test_no_key_in_public_settings(self):
        result = settings()
        self.assertTrue(result['generation'])
        self.assertEqual(len(result['models']), 5)
        self.assertNotIn('unit-test-placeholder', json.dumps(result))

    def test_no_key_disables_generation(self):
        os.environ['GEMINI_API_KEY'] = ' '
        self.assertFalse(settings()['generation'])

    def test_unconfigured_model_never_calls_provider(self):
        with patch('app.llm.urlopen') as call:
            with self.assertRaises(GenerationError):
                generate('s', 'q', [], '../../invalid')
            call.assert_not_called()

    def test_quota_error_does_not_expose_provider_body(self):
        error = HTTPError('https://example.invalid', 429, 'secret-details', {}, None)
        with patch('app.llm.urlopen', side_effect=error):
            with self.assertRaisesRegex(GenerationError, 'Quota or rate limit') as caught:
                generate('s', 'q', [])
            self.assertNotIn('secret-details', str(caught.exception))

    def test_blocked_or_invalid_response(self):
        for payload in [{'promptFeedback': {'blockReason': 'SAFETY'}}, {'candidates': [{'finishReason': 'MAX_TOKENS'}]}, {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': 'not json'}]}}]}]:
            with patch('app.llm.urlopen', return_value=self.response(payload)):
                with self.assertRaises(GenerationError):
                    generate('s', 'q', [])

    def test_openai_compatibility(self):
        os.environ.update(LLM_PROVIDER='openai', OPENAI_API_KEY='test-openai')
        payload = {'choices': [{'message': {'content': '{"claims":[]}'}}]}
        with patch('app.llm.urlopen', return_value=self.response(payload)) as call:
            self.assertEqual(generate('s', 'q', []), {'claims': []})
            self.assertEqual(call.call_args.args[0].get_header('Authorization'), 'Bearer test-openai')

    def test_invalid_router_pool(self):
        os.environ['GEMINI_ROUTER_MODELS'] = '../../invalid'
        with self.assertRaises(GenerationError):
            settings()
