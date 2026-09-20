from dotenv import load_dotenv
import os
import groq

load_dotenv()
key = os.getenv('GROQ_API_KEY')
print('GROQ_API_KEY present:', bool(key))
client = groq.Groq(api_key=key)
models = client.models.list()
print('total models:', len(models.data))
print('embedding-capable models:')
for model in models.data:
    output = getattr(model, 'output_modalities', None)
    if output and 'embedding' in output:
        print('  ', model.id, 'name=', getattr(model, 'name', None), 'input=', getattr(model, 'input_modalities', None), 'output=', output)
