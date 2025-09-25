import sqlite3
import os
import re
from datetime import datetime

# Input and output paths
input_file = r"E:\TM2_LU_2023_Full\emme_project\Logbook\project.mlbk"
output_file = r"E:\TM2_LU_2023_Full\emme_project\emme_logbook.txt"

def export_logbook_to_text(input_file, output_file):
    conn = sqlite3.connect(input_file)
    cursor = conn.cursor()
    
    # Get all documents (sessions) with their elements and attributes
    query = """
    SELECT 
        d.document_id,
        d.title as session_title,
        e.element_id,
        e.parent_id,
        e.tag,
        e.text,
        a.name as attr_name,
        a.value as attr_value
    FROM documents d
    LEFT JOIN elements e ON d.document_id = e.document_id
    LEFT JOIN attributes a ON e.element_id = a.element_id
    ORDER BY d.document_id, e.element_id, a.name
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    
    with open(output_file, "w", encoding="utf-8") as f:
        current_session = None
        current_element = None
        element_data = {}
        
        for row in results:
            doc_id, session_title, elem_id, parent_id, tag, text, attr_name, attr_value = row
            
            # New session
            if current_session != doc_id:
                if current_session is not None:
                    # Write the last element if exists
                    if current_element is not None:
                        write_element_to_file(f, element_data)
                
                current_session = doc_id
                current_element = None
                element_data = {}
                
                f.write("=" * 60 + "\n")
                f.write(f"SESSION: {session_title}\n")
                f.write("=" * 60 + "\n")
            
            # New element within session
            if elem_id and current_element != elem_id:
                # Write previous element if exists
                if current_element is not None:
                    write_element_to_file(f, element_data)
                
                current_element = elem_id
                element_data = {
                    'element_id': elem_id,
                    'parent_id': parent_id,
                    'tag': tag,
                    'text': text,
                    'attributes': {}
                }
            
            # Add attribute to current element
            if attr_name and attr_value and current_element:
                element_data['attributes'][attr_name] = attr_value
        
        # Write the last element
        if current_element is not None:
            write_element_to_file(f, element_data)
    
    conn.close()
    print(f"Logbook exported to: {output_file}")

def write_element_to_file(f, element_data):
    """Write a single element's data to the output file"""
    if not element_data:
        return
        
    tag = element_data.get('tag', '')
    text = element_data.get('text', '')
    attributes = element_data.get('attributes', {})
    
    # Skip elements that are just containers or have no meaningful content
    if not tag and not text and not attributes:
        return
    
    # Extract timestamp from attributes
    timestamp = ""
    for attr_name, attr_value in attributes.items():
        if attr_name.startswith('begin_') and attr_value:
            timestamp = attr_value
            break
    
    # Write element information
    if tag:
        f.write(f"Action: {tag}\n")
    
    if timestamp:
        f.write(f"Time: {timestamp}\n")
    
    # Write other meaningful attributes
    for attr_name, attr_value in attributes.items():
        if not attr_name.startswith('begin_') and not attr_name.startswith('end_') and not attr_name.startswith('cookie_'):
            if attr_name == 'project':
                f.write(f"Project: {attr_value}\n")
            elif attr_name == 'self':
                f.write(f"Module: {attr_value}\n")
            elif attr_value and len(str(attr_value)) < 200:  # Avoid very long attribute values
                f.write(f"{attr_name}: {attr_value}\n")
    
    # Write text content (clean HTML if present)
    if text:
        clean_text = clean_html_content(text)
        if clean_text.strip():
            f.write(f"Description: {clean_text}\n")
    
    f.write("-" * 40 + "\n")

def clean_html_content(text):
    """Clean HTML content to extract meaningful text"""
    if not text:
        return ""
    
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    
    # Remove script content
    clean = re.sub(r'<script.*?</script>', '', clean, flags=re.DOTALL)
    
    # Clean up whitespace
    clean = re.sub(r'\s+', ' ', clean)
    clean = clean.strip()
    
    return clean

if __name__ == "__main__":
    export_logbook_to_text(input_file, output_file)