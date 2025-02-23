from flask import Flask, request, jsonify
from http import HTTPStatus
import requests
import os
from dotenv import load_dotenv
import ollama
import time

load_dotenv()

app = Flask(__name__)

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

# Validate API key is set
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# Define available models with their providers
AVAILABLE_MODELS = [
    {"id": "deepseek-ai/DeepSeek-R1", "name": "DeepSeek R1", "provider": "huggingface"},
    {"id": "mistralai/Mixtral-8x7B-Instruct-v0.1", "name": "Mixtral 8x7B", "provider": "huggingface"},
    {"id": "meta-llama/Llama-2-70b-chat-hf", "name": "Llama2 70B", "provider": "huggingface"},
    {"id": "mixtral", "name": "Mixtral (Local)", "provider": "ollama"},
    {"id": "llama2", "name": "Llama2 (Local)", "provider": "ollama"},
    {"id": "mistral", "name": "Mistral (Local)", "provider": "ollama"}
]

def try_huggingface(model, prompt):
    """Try to get a response from Hugging Face"""
    response = requests.post(
        'https://huggingface.co/api/inference-proxy/together/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json'
        },
        json={
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 500,
            'stream': False
        }
    )
    
    if response.status_code != 200:
        raise Exception(f'API error: {response.text}')
        
    data = response.json()
    return data['choices'][0]['message']['content']

def try_ollama(model, prompt):
    """Try to get a response from Ollama"""
    try:
        response = ollama.chat(model=model, messages=[
            {'role': 'user', 'content': prompt}
        ])
        return response['message']['content']
    except Exception as e:
        raise Exception(f'Ollama error: {str(e)}')

@app.route('/')
def index():
    # Generate radio buttons HTML from the models list
    model_options = '\n'.join([
        f'''
        <label>
            <input type="radio" name="model" value="{model['id']}" {"checked" if i==0 else ""}> 
            {model['name']}
        </label>'''
        for i, model in enumerate(AVAILABLE_MODELS)
    ])

    return f'''
    <html>
        <head>
            <title>AI Chat Interface</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    max-width: 800px; 
                    margin: 40px auto; 
                    padding: 20px;
                }}
                textarea {{ 
                    width: 100%; 
                    height: 150px; 
                    margin: 10px 0;
                }}
                button {{
                    padding: 10px 20px;
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    cursor: pointer;
                }}
                #response {{
                    white-space: pre-wrap;
                    background-color: #f5f5f5;
                    padding: 15px;
                    margin-top: 20px;
                }}
                .hint {{
                    color: #666;
                    font-size: 0.9em;
                    margin-top: 5px;
                }}
                .model-select {{
                    margin: 10px 0;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                }}
                .model-select label {{
                    background: #f0f0f0;
                    padding: 8px 15px;
                    border-radius: 15px;
                    cursor: pointer;
                }}
                .model-select label:hover {{
                    background: #e0e0e0;
                }}
                @keyframes blink {{
                    0% {{ opacity: .2; }}
                    20% {{ opacity: 1; }}
                    100% {{ opacity: .2; }}
                }}
                .loading span {{
                    animation-name: blink;
                    animation-duration: 1.4s;
                    animation-iteration-count: infinite;
                    animation-fill-mode: both;
                }}
                .loading span:nth-child(2) {{
                    animation-delay: .2s;
                }}
                .loading span:nth-child(3) {{
                    animation-delay: .4s;
                }}
            </style>
        </head>
        <body>
            <h1>AI Chat Interface</h1>
            
            <div class="model-select">
                {model_options}
            </div>

            <textarea id="prompt" placeholder="Enter your prompt here..."></textarea>
            <div class="hint">Press Enter to send, Shift+Enter for new line</div>
            <button onclick="sendPrompt()">Send</button>
            <div id="response"></div>

            <script>
                const promptTextarea = document.getElementById('prompt');
                const response = document.getElementById('response');

                function getSelectedModel() {{
                    return document.querySelector('input[name="model"]:checked').value;
                }}

                function setLoading() {{
                    response.innerHTML = 'Thinking<span>.</span><span>.</span><span>.</span>';
                    response.className = 'loading';
                }}

                function setResponse(text) {{
                    response.textContent = text;
                    response.className = '';
                }}

                async function sendPrompt() {{
                    const prompt = promptTextarea.value;
                    if (!prompt.trim()) return;  // Don't send empty prompts
                    
                    try {{
                        setLoading();
                        const res = await fetch('/deepseek/', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify({{ 
                                prompt,
                                model: getSelectedModel()
                            }})
                        }});
                        
                        const data = await res.json();
                        setResponse(data.content || data.error);
                        promptTextarea.value = '';  // Clear the input after sending
                    }} catch (error) {{
                        setResponse('Error: ' + error.message);
                    }}
                }}

                // Handle keyboard events
                promptTextarea.addEventListener('keydown', function(e) {{
                    if (e.key === 'Enter') {{
                        // If Shift key is pressed, allow new line
                        if (e.shiftKey) {{
                            return;
                        }}
                        
                        // For both regular Enter and Ctrl+Enter
                        e.preventDefault();
                        sendPrompt();
                    }}
                }});
            </script>
        </body>
    </html>
    '''

@app.route('/deepseek/', methods=['POST'])
def deepseek():
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        model_id = data.get('model', AVAILABLE_MODELS[0]['id'])
        
        if not prompt:
            return jsonify({
                'error': 'Prompt is required.'
            }), HTTPStatus.BAD_REQUEST

        # Find the model configuration
        model_config = next((m for m in AVAILABLE_MODELS if m['id'] == model_id), None)
        if not model_config:
            return jsonify({
                'error': 'Invalid model selected.'
            }), HTTPStatus.BAD_REQUEST

        print(f"\nReceived prompt: {prompt}")
        print(f"Using model: {model_id} ({model_config['provider']})")

        errors = []
        
        # Try primary provider
        try:
            if model_config['provider'] == 'huggingface':
                content = try_huggingface(model_id, prompt)
            else:
                content = try_ollama(model_id, prompt)
            return jsonify({'content': content})
        except Exception as e:
            errors.append(str(e))
            print(f"Primary provider failed: {str(e)}")

            # If Hugging Face fails, try Ollama equivalent
            if model_config['provider'] == 'huggingface':
                try:
                    # Map HF models to Ollama equivalents
                    ollama_fallbacks = {
                        'deepseek-ai/DeepSeek-R1': 'mixtral',
                        'mistralai/Mixtral-8x7B-Instruct-v0.1': 'mixtral',
                        'meta-llama/Llama-2-70b-chat-hf': 'llama2'
                    }
                    fallback_model = ollama_fallbacks.get(model_id, 'mistral')
                    print(f"Trying Ollama fallback with model: {fallback_model}")
                    content = try_ollama(fallback_model, prompt)
                    return jsonify({
                        'content': content,
                        'note': 'Used fallback model due to primary provider error'
                    })
                except Exception as e2:
                    errors.append(str(e2))
                    print(f"Fallback also failed: {str(e2)}")

        # If all attempts failed
        return jsonify({
            'error': f'All providers failed: {"; ".join(errors)}'
        }), HTTPStatus.BAD_GATEWAY

    except Exception as e:
        print(f"Internal error: {str(e)}")
        return jsonify({
            'error': f'Internal server error: {str(e)}'
        }), HTTPStatus.INTERNAL_SERVER_ERROR

if __name__ == '__main__':
    # In production, use a proper WSGI server and set debug=False
    app.run(debug=False)

