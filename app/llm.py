"""Server-side Gemini/OpenAI generation; credentials never reach the browser."""
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GEMINI_MODELS = ['gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-pro-preview', 'gemini-3.7-flash', 'gemini-3.6-flash']
SCHEMA = {'type': 'object', 'properties': {'claims': {'type': 'array', 'items': {
    'type': 'object', 'properties': {k: {'type': 'string'} for k in ['statement', 'source_id', 'quote']},
    'required': ['statement', 'source_id', 'quote']}}}, 'required': ['claims']}


class GenerationError(Exception):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def settings():
    provider = os.getenv('LLM_PROVIDER', 'gemini').strip().lower()
    if provider not in {'gemini', 'openai'}:
        raise GenerationError('LLM_PROVIDER must be gemini or openai.')
    if provider == 'gemini':
        models = list(dict.fromkeys(m.strip() for m in os.getenv('GEMINI_ROUTER_MODELS', ','.join(GEMINI_MODELS)).split(',') if m.strip()))
        default = models[0] if models else ''
        key = os.getenv('GEMINI_API_KEY', '').strip()
    else:
        default = os.getenv('OPENAI_MODEL', 'gpt-4o-mini').strip()
        models = [default]
        key = os.getenv('OPENAI_API_KEY', '').strip()
    if not models or default not in models or any(not re.fullmatch(r'[A-Za-z0-9._-]+', m) for m in models):
        raise GenerationError('Invalid model configuration. The default model must be in the model list.')
    return {'provider': provider, 'models': models, 'default_model': default, 'generation': bool(key), 'routing': 'automatic'}


def generate(system, question, sources, model=None, timeout=30):
    config = settings()
    model = model or config['default_model']
    if model not in config['models']:
        raise GenerationError('Choose a model from the configured list.')
    provider = config['provider']
    key = os.getenv('GEMINI_API_KEY' if provider == 'gemini' else 'OPENAI_API_KEY', '').strip()
    if not key:
        raise GenerationError(f'Add your {provider} API key to .env and restart the server.')
    content = json.dumps({'question': question, 'sources': sources})
    if provider == 'gemini':
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
        headers = {'x-goog-api-key': key}
        body = {'systemInstruction': {'parts': [{'text': system}]}, 'contents': [
            {'role': 'user', 'parts': [{'text': content}]}],
            'generationConfig': {'responseFormat': {'text': {'mimeType': 'application/json', 'schema': SCHEMA}}}}
    else:
        url = 'https://api.openai.com/v1/chat/completions'
        headers = {'Authorization': f'Bearer {key}'}
        body = {'model': model, 'response_format': {'type': 'json_object'}, 'messages': [
            {'role': 'system', 'content': system}, {'role': 'user', 'content': content}]}
    request = Request(url, data=json.dumps(body).encode(), headers={**headers, 'Content-Type': 'application/json'}, method='POST')
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        if provider == 'gemini':
            candidate = data['candidates'][0]
            if candidate.get('finishReason') != 'STOP':
                raise GenerationError('Gemini did not return a complete answer. Try rephrasing your question.')
            text = ''.join(part.get('text', '') for part in candidate['content']['parts'] if not part.get('thought'))
        else:
            text = data['choices'][0]['message']['content']
        payload = json.loads(text)
        if not isinstance(payload, dict) or not isinstance(payload.get('claims'), list):
            raise ValueError('Invalid claims')
        usage = data.get('usageMetadata', {}) if provider == 'gemini' else data.get('usage', {})
        total = usage.get('totalTokenCount') if provider == 'gemini' else usage.get('total_tokens')
        if isinstance(total, int):
            payload['_usage'] = {'total_tokens': total, 'scope': 'successful response only'}
        return payload
    except HTTPError as exc:
        messages = {400: 'The provider rejected the request. Check your API key and model configuration.',
                    401: 'API key is invalid. Update .env and restart.',
                    403: 'Access denied. Check your API key, project permissions and model access.',
                    404: 'Model unavailable for this account.',
                    429: 'Quota or rate limit reached. Wait and retry, or check your API plan.'}
        raise GenerationError(messages.get(exc.code, 'The AI provider is temporarily unavailable. Try again later.'), retryable=exc.code in {404, 500, 502, 503, 504}) from None
    except (URLError, TimeoutError):
        raise GenerationError('Could not reach the AI provider. Check your connection and try again.', retryable=True) from None
    except (ValueError, KeyError, IndexError, TypeError):
        raise GenerationError('No valid structured answer returned. Try rephrasing your question.') from None


def route(question, sources, available):
    """Transparent heuristic; does not measure which model is objectively best."""
    text = question.lower()
    word_count = len(question.split())
    context_size = sum(len(s.get('text', '')) for s in sources)
    if re.search(r'\b(compare|contrast|analy[sz]e|evaluate|trade.?offs?|justify|infer|contradict|reconcile)\b', text) or word_count > 90:
        preferred, reason = 'gemini-3.1-pro-preview', 'Complex reasoning or comparison'
    elif re.search(r'\b(code|debug|algorithm|sql|python|javascript|implementation)\b', text):
        preferred, reason = 'gemini-3.7-flash', 'Technical or code-related question'
    elif context_size > 18000 or word_count > 45:
        preferred, reason = 'gemini-3.8-flash', 'Long question or large retrieved context'
    elif re.search(r'\b(summari[sz]e|summary|explain|outline|overview)\b', text):
        preferred, reason = 'gemini-3.6-flash', 'Explanation or summary'
    elif word_count <= 25:
        preferred, reason = 'gemini-3.5-flash-lite', 'Short factual question'
    else:
        preferred, reason = 'gemini-3.8-flash', 'General document question'
    order = list(dict.fromkeys([preferred, *GEMINI_MODELS, *available]))
    return [model for model in order if model in available], reason


def generate_auto(system, question, sources, routing_question=None):
    config = settings()
    order, reason = route(routing_question or question, sources, config['models'])
    if config['provider'] != 'gemini':
        order, reason = config['models'], 'Configured provider'
    deadline = time.monotonic() + 90
    attempted = []
    last_error = None
    for model in order[:5]:
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            break
        attempted.append(model)
        try:
            payload = generate(system, question, sources, model, timeout=min(30, remaining))
            return payload, {'model': model, 'routing_reason': reason,
                             'fallback_used': len(attempted) > 1, 'attempted_models': attempted, 'usage': payload.pop('_usage', None)}
        except GenerationError as exc:
            exc.attempted_models = attempted.copy()
            last_error = exc
            # Do not rotate models to work around quota, permission or safety blocks.
            if not exc.retryable:
                raise
    error = GenerationError('Automatic selection could not obtain an answer. ' + str(last_error or 'Request time budget exhausted.'))
    error.attempted_models = attempted
    raise error
