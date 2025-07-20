import os
from flask import Flask, request, render_template_string, redirect, url_for, session
from supabase import create_client, Client
from flask_session import Session
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
app.config['PORT'] = int(os.environ.get('PORT', 5000))
Session(app)

# Initialize Supabase client
supabase: Client = create_client(os.environ.get('SUPABASE_URL'), os.environ.get('SUPABASE_KEY'))

# HTML templates
LOGIN_TEMPLATE = """
<h2>Login</h2>
{% if error %}
    <p style="color: red;">{{ error }}</p>
{% endif %}
<form method="POST" action="{{ url_for('login', next=next) }}">
    <label>Email: <input type="email" name="email" required></label><br>
    <label>Password: <input type="password" name="password" required></label><br>
    <input type="submit" value="Login">
</form>
"""

UPLOAD_FORM_TEMPLATE = """
<h2>Upload Photo for {{ id }}</h2>
{% if error %}
    <p style="color: red;">{{ error }}</p>
{% endif %}
<form method="POST" enctype="multipart/form-data" action="{{ url_for('upload', id=id) }}">
    <input type="file" id="fileInput" name="photo" accept="image/*" style="display:none">
    <input type="file" id="cameraInput" name="photo" accept="image/*" capture="environment" style="display:none">
    <button type="button" onclick="document.getElementById('fileInput').click()">📁 Choose from Files</button>
    <button type="button" onclick="document.getElementById('cameraInput').click()">📷 Take Photo</button>
    <div id="previewContainer" style="margin-top: 1em; display: none;">
        <img id="previewImage" src="#" alt="Image Preview" style="max-width: 100%; height: auto; border: 1px solid #ccc;"><br><br>
        <button type="button" onclick="clearImage()">❌ Remove Photo</button>
    </div>
    <div style="margin-top: 1em;">
        <input type="submit" value="✅ Upload Photo">
    </div>
</form>
<p><a href="{{ url_for('logout') }}">Logout</a></p>

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
{% if error %}
    <p style="color: red;">{{ error }}</p>
{% endif %}
<form method="POST" action="{{ url_for('delete_photo', id=id) }}">
    <input type="submit" value="Delete Photo" onclick="return confirm('Are you sure you want to delete this photo?');">
</form>
<a href="{{ url_for('logout') }}">Logout</a>
"""

def require_auth(f):
    def decorated(*args, **kwargs):
        if 'user' not in session:
            next_url = request.url
            return redirect(url_for('login', next=next_url))
        try:
            supabase.auth.get_user(session.get('access_token'))
        except Exception as e:
            print(f"Token validation error: {str(e)}")
            if 'refresh_token' in session:
                try:
                    response = supabase.auth.refresh_session(session['refresh_token'])
                    if response.session:
                        session['access_token'] = response.session.access_token
                        session['refresh_token'] = response.session.refresh_token
                        supabase.postgrest.auth(response.session.access_token)
                    else:
                        session.pop('user', None)
                        session.pop('access_token', None)
                        session.pop('refresh_token', None)
                        return redirect(url_for('login', next=request.url))
                except Exception as e:
                    print(f"Token refresh error: {str(e)}")
                    session.pop('user', None)
                    session.pop('access_token', None)
                    session.pop('refresh_token', None)
                    return redirect(url_for('login', next=request.url))
            else:
                session.pop('user', None)
                session.pop('access_token', None)
                return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next', url_for('photo', id='default'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            response = supabase.auth.sign_in_with_password({'email': email, 'password': password})
            if response.user:
                session['user'] = response.user.id
                session['access_token'] = response.session.access_token
                session['refresh_token'] = response.session.refresh_token
                session.permanent = True
                supabase.postgrest.auth(response.session.access_token)
                return redirect(next_url)
            else:
                return render_template_string(LOGIN_TEMPLATE, error="Invalid credentials. Please try again.", next=next_url)
        except Exception as e:
            print(f"Login error: {str(e)}")
            return render_template_string(LOGIN_TEMPLATE, error=f"Login failed: {str(e)}. Please try again.", next=next_url)
    return render_template_string(LOGIN_TEMPLATE, error=None, next=next_url)

@app.route('/logout')
def logout():
    next_url = request.args.get('next', url_for('login'))
    session.pop('user', None)
    session.pop('access_token', None)
    session.pop('refresh_token', None)
    supabase.auth.sign_out()
    return redirect(next_url)

@app.route('/photo/<id>')
@require_auth
def photo(id):
    file_path = f"Uploads/{id}.jpg"
    bucket_name = 'photos'
    try:
        files = supabase.storage.from_(bucket_name).list(path="Uploads")
        file_exists = any(file['name'] == f"{id}.jpg" for file in files)
        
        if file_exists:
            image_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
            return render_template_string(VIEW_PHOTO_TEMPLATE, id=id, image_url=image_url, error=None)
        else:
            return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error=None)
    except Exception as e:
        print(f"Error checking file: {str(e)}")
        return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error="Failed to check for existing photo. Please try uploading.")

@app.route('/upload/<id>', methods=['POST'])
@require_auth
def upload(id):
    if 'photo' not in request.files:
        return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error="No photo uploaded. Please select a file and try again.")
    
    photo = request.files['photo']
    if photo.filename == '':
        return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error="No file selected. Please select a file and try again.")
    
    if photo:
        try:
            print("Received file:", photo.filename, photo.content_type)
            file_path = f"Uploads/{id}.jpg"
            bucket_name = 'photos'

            if not photo.content_type.startswith('image/'):
                return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error="Only image files are allowed. Please select an image and try again.")

            file_content = photo.read()
            if len(file_content) > 2 * 1024 * 1024:
                return render_template_string(UPLOAD_FORM_TEMPLATE, id=id, error="File too large. Maximum size is 2MB. Please select a smaller file and try again.")

            print("Uploading to path:", file_path)
            response = supabase.storage.from_(bucket_name).upload(
                file_path,
                file_content,
                {
                    'content-type': photo.content_type,
                    'upsert': 'true'
                }
            )

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

@app.route('/delete/<id>', methods=['POST'])
@require_auth
def delete_photo(id):
    file_path = f"Uploads/{id}.jpg"
    bucket_name = 'photos'
    try:
        supabase.storage.from_(bucket_name).remove([file_path])
        print(f"Deleted photo: {file_path}")
        return redirect(url_for('photo', id=id))
    except Exception as e:
        print(f"Delete error: {str(e)}")
        error_message = f"Error deleting photo: {str(e)}. Please try again."
        if "row-level security" in str(e).lower():
            error_message = "Delete failed due to storage permission settings. Please try again or contact support."
        return render_template_string(VIEW_PHOTO_TEMPLATE, id=id, image_url=supabase.storage.from_(bucket_name).get_public_url(file_path), error=error_message)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=False)