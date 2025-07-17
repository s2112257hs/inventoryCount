from flask import Flask, request, render_template_string, redirect, url_for
from supabase import create_client, Client

app = Flask(__name__)

# Initialize Supabase client
SUPABASE_URL = 'https://piqzzdrerzfhmqhumzxc.supabase.co'  # e.g., https://your_project_id.supabase.co
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBpcXp6ZHJlcnpmaG1xaHVtenhjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIyNjY1MDUsImV4cCI6MjA2Nzg0MjUwNX0.2eOimozU0BHy4uTl9TsA4fyQPBC1qUm-_K3DECuZTuQ'
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# HTML templates
UPLOAD_FORM_TEMPLATE = """
<h2>Upload Photo for {{ id }}</h2>
{% if error %}
    <p style="color: red;">{{ error }}</p>
{% endif %}
<form method="POST" enctype="multipart/form-data" action="{{ url_for('upload', id=id) }}">
    <!-- Hidden file inputs -->
    <input type="file" id="fileInput" name="photo" accept="image/*" style="display:none">
    <input type="file" id="cameraInput" name="photo" accept="image/*" capture="environment" style="display:none">

    <!-- Visible buttons -->
    <button type="button" onclick="document.getElementById('fileInput').click()">📁 Choose from Files</button>
    <button type="button" onclick="document.getElementById('cameraInput').click()">📷 Take Photo</button>

    <!-- Preview Section -->
    <div id="previewContainer" style="margin-top: 1em; display: none;">
        <img id="previewImage" src="#" alt="Image Preview" style="max-width: 100%; height: auto; border: 1px solid #ccc;"><br><br>
        <button type="button" onclick="clearImage()">❌ Remove Photo</button>
    </div>

    <!-- Submit Section -->
    <div style="margin-top: 1em;">
        <input type="submit" value="✅ Upload Photo">
    </div>
</form>

<script>
    const fileInput = document.getElementById('fileInput');
    const cameraInput = document.getElementById('cameraInput');
    const previewContainer = document.getElementById('previewContainer');
    const previewImage = document.getElementById('previewImage');

    function handleImage(input) {
        try {
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    previewImage.src = e.target.result;
                    previewContainer.style.display = 'block';
                };
                reader.onerror = function(e) {
                    console.error('Error reading file:', e);
                };
                reader.readAsDataURL(input.files[0]);
            } else {
                console.error('No file selected');
            }
        } catch (error) {
            console.error('Error in handleImage:', error);
        }
    }

    fileInput.onchange = () => handleImage(fileInput);
    cameraInput.onchange = () => handleImage(cameraInput);

    function clearImage() {
        try {
            fileInput.value = "";
            cameraInput.value = "";
            previewImage.src = "#";
            previewContainer.style.display = 'none';
        } catch (error) {
            console.error('Error clearing image:', error);
        }
    }
</script>
"""

VIEW_PHOTO_TEMPLATE = """
<h2>Photo for {{ id }}</h2>
<img src="{{ image_url }}" width="300"><br><br>
"""

@app.route('/photo/<id>')
def photo(id):
    file_path = f"uploads/{id}.jpg"
    bucket_name = 'photos'
    try:
        # Check if the file exists in the bucket
        files = supabase.storage.from_(bucket_name).list(path="uploads")
        file_exists = any(file['name'] == f"{id}.jpg" for file in files)
        
        if file_exists:
            # Get public URL for the existing file
            image_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
            return render_template_string(VIEW_PHOTO_TEMPLATE, id=id, image_url=image_url)
        else:
            # File doesn't exist, show upload form
            return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error=None)
    except Exception as e:
        print(f"Error checking file: {str(e)}")
        return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error="Failed to check for existing photo. Please try uploading.")

@app.route('/upload/<id>', methods=['POST'])
def upload(id):
    if 'photo' not in request.files:
        return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error="No photo uploaded. Please select a file and try again.")
    
    photo = request.files['photo']
    if photo.filename == '':
        return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error="No file selected. Please select a file and try again.")
    
    if photo:
        try:
            print("Received file:", photo.filename, photo.content_type)
            # Generate file path for Supabase
            file_path = f"uploads/{id}.jpg"
            bucket_name = 'photos'

            # Validate file type
            if not photo.content_type.startswith('image/'):
                return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error="Only image files are allowed. Please select an image and try again.")

            # Read the file content
            file_content = photo.read()

            # Check file size (e.g., 5MB limit)
            if len(file_content) > 5 * 1024 * 1024:
                return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error="File too large. Maximum size is 5MB. Please select a smaller file and try again.")

            print("Uploading to path:", file_path)
            # Upload to Supabase Storage
            response = supabase.storage.from_(bucket_name).upload(
                file_path,
                file_content,
                {
                    'content-type': photo.content_type,
                    'upsert': 'true'
                }
            )

            # Check for upload success
            print("Upload response:", response)
            if hasattr(response, 'path') and response.path == file_path:
                print("Upload successful, redirecting to /photo/", id)
                return redirect(url_for('photo', id=id))
            else:
                error_message = "Upload failed: Unknown error. Please try uploading again."
                if hasattr(response, 'error') and response.error:
                    error_message = f"Upload failed: {response.error}. Please try uploading again."
                if "row-level security" in str(response).lower():
                    error_message = "Upload failed due to storage permission settings. Please try uploading again or contact support."
                print("Upload failed:", error_message)
                return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error=error_message)

        except Exception as e:
            print(f"Supabase error: {str(e)}")
            error_message = f"Error uploading to Supabase: {str(e)}. Please try uploading again."
            if "row-level security" in str(e).lower():
                error_message = "Upload failed due to storage permission settings. Please try uploading again or contact support."
            return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error=error_message)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
