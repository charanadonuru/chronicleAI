from flask import Flask, render_template, request, jsonify
import re
import random
from model import generate_titles_makemore

app = Flask(__name__)

def filter_titles(titles_data):
    """
    Applies automatic filters to the generated titles list.
    """
    filtered = []
    seen = set()
    
    for item in titles_data:
        title = item["title"]
        
        # 1. Trim extra spaces & capitalize words automatically (Title Case)
        # Assuming you want to capitalize words nicely, string.title() works for English mockups.
        clean_title = " ".join(title.split()).title()
        
        # 2. Check length (4 to 60 characters)
        if len(clean_title) < 4 or len(clean_title) > 60:
            continue
            
        # 3. Check repeated words
        words = clean_title.lower().split()
        if len(words) != len(set(words)):
            continue
            
        # 4. Remove duplicates
        if clean_title.lower() in seen:
            continue
            
        seen.add(clean_title.lower())
        
        item["title"] = clean_title
        filtered.append(item)
        
    return filtered


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    prefix = data.get('prefix', '').strip()
    temperature = float(data.get('temperature', 0.8))
    num_titles = int(data.get('num_titles', 5))
    
    # 1. Generate (Mock up)
    generated = generate_titles_makemore(prefix, temperature, num_titles * 2) 
    
    # 2. Filter
    filtered = filter_titles(generated)
    
    # 3. Return the exact requested count
    final_titles = filtered[:num_titles]
    
    return jsonify({
        "success": True,
        "titles": final_titles,
        "temperature": temperature
    })

@app.route('/compare', methods=['POST'])
def compare():
    data = request.json
    prefix = data.get('prefix', '').strip()
    
    modes = {
        "Conservative": 0.5,
        "Balanced": 0.8,
        "Creative": 1.2
    }
    
    compare_results = []
    
    for mode_name, temp in modes.items():
        # Generate enough to make sure we find one that passes the filter
        generated = generate_titles_makemore(prefix, temp, 5)
        filtered = filter_titles(generated)
        
        if filtered:
            selected_title = filtered[0]
            compare_results.append({
                "mode": mode_name,
                "title": selected_title["title"],
                "confidence": selected_title["confidence"],
                "temperature": temp
            })
    
    return jsonify({
        "success": True,
        "compare_results": compare_results
    })


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)
