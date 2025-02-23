# AI Chat Interface using Flask

```bash
pip install -r requirements.txt
python app.py
```

```bash 
curl -X POST http://127.0.0.1:5000/deepseek/ \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the capital of France?",
    "model": "deepseek-ai/DeepSeek-R1"
  }'
```

