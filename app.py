from flask import Flask, render_template, request, jsonify, send_file, url_for
import os
import base64
from PIL import Image
import io
from main import get_math_explanation, create_video_from_steps
from werkzeug.utils import secure_filename
from google import genai
from google.genai import types

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'videos')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize Gemini
client = genai.Client(api_key="AIzaSyB_W9t18sgLbGXoD_zeqPaLkF8oyPPO19g")

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze_whiteboard', methods=['POST'])
def analyze_whiteboard():
    try:
        # Get the image data and query from the request
        data = request.json
        image_data = data.get('image')
        query = data.get('query')

        if not image_data or not query:
            return jsonify({'error': 'Missing image or query'}), 400

        # Convert base64 image to PIL Image
        image_data = image_data.split(',')[1]  # Remove data URL prefix
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        # Generate response using Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                image,
                "You are a helpful math tutor. Analyze the whiteboard content and answer the following question: " + query
            ],
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=1000
            )
        )

        return jsonify({'response': response.text})

    except Exception as e:
        print(f"Error in analyze_whiteboard: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/explain', methods=['POST'])
def explain():
    try:
        question = request.form.get('question')
        if not question:
            return jsonify({'error': 'No question provided'}), 400

        # Get explanation steps
        steps = get_math_explanation(question)
        
        # Generate a secure filename
        safe_filename = secure_filename(question[:30].replace(' ', '_'))
        video_filename = f'explanation_{safe_filename}.mp4'
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
        
        # Generate video
        create_video_from_steps(steps, video_path)
        
        # Create URL for video
        video_url = url_for('static', filename=f'videos/{video_filename}')
        
        # Prepare response
        response = {
            'steps': steps,
            'video_path': video_url
        }
        
        return jsonify(response)
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 