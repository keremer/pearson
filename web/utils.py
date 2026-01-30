"""
Utility functions for the web interface.
"""
import os
from werkzeug.utils import secure_filename

def allowed_file(filename, allowed_extensions={'md'}):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_uploaded_file(file, upload_folder):
    """Save an uploaded file securely."""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        return file_path
    return None