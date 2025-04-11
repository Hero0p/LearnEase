import json
import os
import tempfile
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip
from google import genai
from google.genai import types
import textwrap
import shutil
import math
import requests
import re
import time

def get_math_explanation(query):
    """AI Tutor for solving math equations and explaining concepts"""
    client = genai.Client(api_key="YOUR_API_KEY")
    
    system_instruction = (
        "You are a Math Tutor specialized in teaching school students. "
        "Follow these STRICT RULES for your response:\n"
        "1. Respond ONLY with valid JSON format\n"
        "2. Use this EXACT structure:\n"
        '{"steps": {\n'
        '  "step1": {"title": "STEP_TITLE", "speech": "FULL_SPEECH_TEXT", "duration": NUMBER},\n'
        '  "step2": {...},\n'
        '  ...\n'
        '}}\n'
        "3. Rules for content:\n"
        "   - 'title' should be very short (3-5 words max)\n"
        "   - 'speech' should be complete spoken explanation\n"
        "   - 'duration' between 3-8 seconds based on speech length\n"
        "4. Formatting rules:\n"
        "   - No line breaks in text values\n"
        "   - Escape all quotes in text with backslash\n"
        "   - No trailing commas\n"
        "5. Mark important concepts with asterisks in the speech text"
    )
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[query],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
                max_output_tokens=1000
            )
        )
        
        # Clean the response to extract proper JSON
        response_text = response.text
        
        # Find the first { and last } to extract the JSON
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        json_str = response_text[json_start:json_end]
        
        # Parse the JSON
        data = json.loads(json_str)
        return data.get('steps', {})
        
    except Exception as e:
        print(f"Error generating response: {e}")
        return {
            "step1": {
                "title": "Error Occurred", 
                "speech": "Some error occurred, please try again later.",
                "duration": 5
            }
        }

def create_slide(title, speech, filename, width=1280, height=720):
    """Create an image slide with title at top and speech in middle"""
    img = Image.new('RGB', (width, height), color=(13, 17, 23))  # Dark background
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("arial.ttf", 48)
        speech_font = ImageFont.truetype("arial.ttf", 36)
    except:
        title_font = ImageFont.load_default()
        speech_font = ImageFont.load_default()

    # Draw title at the top
    title_lines = textwrap.wrap(title, width=30)
    y_text = height // 8  # Position at top
    for line in title_lines:
        draw.text(((width - draw.textlength(line, font=title_font)) // 2, y_text), 
                 line, font=title_font, fill=(255, 255, 255))
        y_text += 60

    # Draw speech text in the middle with formatting
    y_text = height // 3  # Middle position
    for line in textwrap.wrap(speech, width=50):
        if '*' in line:
            parts = line.split('*')
            x_pos = (width - sum(draw.textlength(part, font=speech_font) for part in parts)) // 2
            for i, part in enumerate(parts):
                color = (255, 215, 0) if i % 2 else (220, 220, 220)
                draw.text((x_pos, y_text), part, font=speech_font, fill=color)
                x_pos += draw.textlength(part, font=speech_font)
            y_text += 45
        else:
            draw.text(((width - draw.textlength(line, font=speech_font)) // 2, y_text), 
                     line, font=speech_font, fill=(220, 220, 220))
            y_text += 45

    img.save(filename)

def text_to_speech(text, filename):
    """Convert text to speech using TopMediai API (speech only)"""
    url = "https://api.topmediai.com/v1/text2speech"
    
    payload = {
        "text": text,
        "speaker": "00151554-3826-11ee-a861-00163e2ac61b",  # Default speaker ID
        "emotion": "Friendly"
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": "f322217059044a3f85a74bc5e9fb33e3"  # Replace with your actual API key
    }

    try:
        # First request to generate the speech
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            audio_url = data.get("data", {}).get("oss_url")
            
            if audio_url:
                # Download the audio file
                audio_response = requests.get(audio_url)
                
                if audio_response.status_code == 200:
                    with open(filename, "wb") as f:
                        f.write(audio_response.content)
                    
                    # Get duration of the audio file
                    audio = AudioFileClip(filename)
                    duration = audio.duration
                    audio.close()
                    return duration
                else:
                    print(f"Error downloading audio: {audio_response.status_code}")
            else:
                print("Audio URL not found in response")
        else:
            print(f"Error in TTS request: {response.status_code}, {response.text}")
            
    except Exception as e:
        print(f"Error in text_to_speech: {e}")
    
    # Fallback: return default duration if TTS fails
    return len(text.split()) / 3  # Approximate duration based on word count

def create_video_from_steps(steps, output_filename="explanation.mp4"):
    """Create video with synchronized audio"""
    temp_dir = tempfile.mkdtemp()
    clips = []
    
    try:
        # Generate slides and audio for each step
        for i, (step_num, step_data) in enumerate(steps.items()):
            title = f"Step {i+1}: {step_data['title']}"
            speech = step_data['speech']
            suggested_duration = step_data.get('duration', 3)
            
            # Create slide with title and speech
            img_filename = os.path.join(temp_dir, f"slide_{i+1}.png")
            create_slide(title, speech, img_filename)
            
            # Generate speech audio (only the speech part)
            audio_filename = os.path.join(temp_dir, f"audio_{i+1}.wav")
            actual_duration = text_to_speech(speech, audio_filename)
            
            # Use the longer of suggested or actual duration
            duration = max(suggested_duration, math.ceil(actual_duration))
            
            # Create clip with image and audio
            clip = ImageClip(img_filename).set_duration(duration)
            audio = AudioFileClip(audio_filename)
            clip = clip.set_audio(audio)
            clips.append(clip)
        
        # Concatenate all clips
        final_clip = concatenate_videoclips(clips, method="compose")
        
        # Write video file
        final_clip.write_videofile(
            output_filename, 
            fps=24,
            codec='libx264', 
            audio_codec='aac',
            threads=4
        )
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    return output_filename

def chat_interface():
    """Interactive chat interface"""
    print("\n" + "="*50)
    print("Math Tutor AI - Enhanced Video Explanation Generator")
    print("="*50)
    print("\nType 'quit' to exit at any time\n")
    
    while True:
        query = input("\nWhat math concept or equation would you like explained?\n> ")
        
        if query.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
            
        print("\nGenerating explanation and video...\n")
        
        try:
            # Get explanation from AI
            steps = get_math_explanation(query)
            
            # Print steps in chat-like format
            for step_num, step_data in steps.items():
                print(f"{step_num}: {step_data['title']}")
                print(f"Explanation: {step_data['speech']}\n")
            
            # Create video with TTS
            video_filename = create_video_from_steps(steps)
            print(f"\nProfessional video created successfully: {video_filename}")
                
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Please try again with a different query.")

if __name__ == "__main__":
    chat_interface()
