import os
import json
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory

# Detect if running on Vercel
is_vercel = os.getenv('VERCEL') == '1'

# Resolve the root directory relative to this file
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if not is_vercel:
    # Load environment variables (passing the exact dotenv file path for safety)
    dotenv_path = os.path.join(root_dir, '.env')
    load_dotenv(dotenv_path)

# Set static_folder to the root directory so both local and Vercel can serve static files
app = Flask(__name__, static_folder=root_dir, static_url_path='')

# Allowed validation sets
ALLOWED_TYPES = {'Email', 'Slack message', 'Text message'}
ALLOWED_TONES = {'Warm', 'Professional', 'Casual', 'Apologetic'}
ALLOWED_LENGTHS = {'Brief', 'Balanced', 'Detailed'}
ALLOWED_MODES = {'Write', 'Refine'}

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Cache-Control'] = 'no-store'
    return response

def validate_draft_request(body):
    if not body or not isinstance(body, dict):
        return 'A JSON request body is required.'
    
    prompt = body.get('prompt')
    message_type = body.get('messageType') or body.get('type')
    tone = body.get('tone')
    length = body.get('length')
    mode = body.get('mode', 'Write')

    if not isinstance(prompt, str) or not prompt.strip():
        return 'Please enter a rough instruction.'
    if len(prompt.strip()) > 1200:
        return 'The instruction must be 1,200 characters or fewer.'
    if message_type not in ALLOWED_TYPES:
        return 'Unsupported message type.'
    if tone not in ALLOWED_TONES:
        return 'Unsupported tone.'
    if length not in ALLOWED_LENGTHS:
        return 'Unsupported length.'
    if mode not in ALLOWED_MODES:
        return 'Unsupported mode.'
    
    return None

def build_messages(prompt, message_type, tone, length, mode):
    active_mode = mode or 'Write'
    
    if active_mode == 'Refine':
        system_content = (
            f"You are Draftly, a careful communications editor. Polish, rewrite, and correct the grammar of the "
            f"user's existing draft to make it a high-quality {message_type}. Adjust the writing style to fit "
            f"the requested tone and length while preserving the user's core message and original meaning. "
            f"First silently assess clarity, tone, politeness, and completeness; then revise the draft once. "
            f"Return valid JSON only, using exactly this schema: "
            f'{{"draft":"the final send-ready message","review":{{"clarity":"short observation","tone":"short observation","completeness":"short observation"}}}}. '
            f"Do not include markdown code fences. Requested tone: {tone}. Requested length: {length}."
        )
    else:
        system_content = (
            f"You are Draftly, a careful communications editor. Create a polished {message_type} from the "
            f"user's rough instruction. First silently assess clarity, tone, politeness, and completeness; "
            f"then revise the draft once. Return valid JSON only, using exactly this schema: "
            f'{{"draft":"the final send-ready message","review":{{"clarity":"short observation","tone":"short observation","completeness":"short observation"}}}}. '
            f"Do not include markdown code fences. Requested tone: {tone}. Requested length: {length}."
        )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": prompt.strip()}
    ]

def parse_groq_json(content):
    try:
        # Strip code block markers if present
        content_str = content.strip()
        if '```' in content_str:
            start = content_str.find('{')
            end = content_str.rfind('}')
            if start != -1 and end != -1:
                content_str = content_str[start:end+1]
        
        parsed = json.loads(content_str)
        if not isinstance(parsed, dict):
            return None
        if not isinstance(parsed.get('draft'), str) or not parsed.get('draft').strip():
            return None
        review = parsed.get('review')
        if not isinstance(review, dict):
            return None
        if (not isinstance(review.get('clarity'), str) or 
            not isinstance(review.get('tone'), str) or 
            not isinstance(review.get('completeness'), str)):
            return None
        return {
            'draft': parsed['draft'].strip(),
            'review': review
        }
    except Exception as e:
        print(f"Error parsing Groq JSON response: {e}")
        return None

@app.route('/')
def serve_index():
    return send_from_directory(root_dir, 'index.html')

@app.route('/api/draft', methods=['POST'])
def draft_api():
    if not request.is_json:
        return jsonify({'error': 'A JSON request body is required.'}), 400
    
    body = request.get_json()
    validation_error = validate_draft_request(body)
    if validation_error:
        return jsonify({'error': validation_error}), 400

    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return jsonify({'error': 'The server is not configured with a Groq API key.'}), 503

    prompt = body.get('prompt')
    message_type = body.get('messageType') or body.get('type')
    tone = body.get('tone')
    length = body.get('length')
    mode = body.get('mode', 'Write')

    # Set higher token limit to prevent truncation, especially when reasoning models use extra tokens for thinking
    max_tokens = 1024 if length == 'Brief' else (2048 if length == 'Detailed' else 1536)

    try:
        payload = {
            'model': os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile'),
            'temperature': 0.55,
            'max_tokens': max_tokens,
            'response_format': {'type': 'json_object'},
            'messages': build_messages(prompt, message_type, tone, length, mode)
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            json=payload,
            headers=headers,
            timeout=30
        )
        
        try:
            groq_data = response.json()
        except Exception:
            groq_data = {}

        if response.status_code != 200:
            print(f"Groq request failed: {response.status_code} {groq_data.get('error', {}).get('message', 'Unknown error')}")
            return jsonify({'error': 'Draft generation is temporarily unavailable. Please try again.'}), (503 if response.status_code == 401 else 502)

        content = groq_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        result = parse_groq_json(content)
        if not result:
            print("Groq returned an invalid draft format.")
            return jsonify({'error': 'The writing service returned an invalid response. Please try again.'}), 502

        return jsonify(result)

    except requests.exceptions.RequestException as e:
        print(f"Groq connection error: {e}")
        return jsonify({'error': 'Could not reach the writing service. Please try again.'}), 502

if __name__ == '__main__':
    PORT = int(os.getenv('PORT', 3000))
    print(f"Draftly is running at http://localhost:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
