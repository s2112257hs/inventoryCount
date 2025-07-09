from flask import Flask, request, send_from_directory, render_template_string, redirect, url_for
import os

app = Flask(__name__)

# Folder where images will be saved
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# HTML templates (basic inline)
UPLOAD_FORM_TEMPLATE = """
<h2>Upload Photo for {{ id }}</h2>
<form method="POST" enctype="multipart/form-data" action="{{ url_for('upload', id=id) }}">
    <!-- Hidden file inputs -->
    <input type="file" id="fileInput" name="photo" accept="image/*" style="display:none" required>
    <input type="file" id="cameraInput" name="photo" accept="image/*" capture="environment" style="display:none" required>

    <!-- Visible buttons -->
    <button type="button" onclick="document.getElementById('fileInput').click()">📁 Choose from Files</button>
    <button type="button" onclick="document.getElementById('cameraInput').click()">📷 Take Photo</button>

    <!-- Preview Section -->
    <div id="previewContainer" style="margin-top: 1em; display: none;">
        <img id="previewImage" src="#" alt="Image Preview" style="max-width: 100%; height: auto; border: 1px solid #ccc;"><br><br>
        <button type="button" onclick="clearImage()">❌ Remove Photo</button>
    </div>

    <!-- Submit Section -->
    <div id="submitSection" style="display:none; margin-top: 1em;">
        <input type="submit" value="✅ Upload Photo">
    </div>

</form>

<script>
    const fileInput = document.getElementById('fileInput');
    const cameraInput = document.getElementById('cameraInput');
    const previewContainer = document.getElementById('previewContainer');
    const previewImage = document.getElementById('previewImage');
    const submitSection = document.getElementById('submitSection');

    function handleImage(input) {
        if (input.files && input.files[0]) {
            const reader = new FileReader();
            reader.onload = function(e) {
                previewImage.src = e.target.result;
                previewContainer.style.display = 'block';
                submitSection.style.display = 'block';
            };
            reader.readAsDataURL(input.files[0]);
        }
    }

    fileInput.onchange = () => handleImage(fileInput);
    cameraInput.onchange = () => handleImage(cameraInput);

    function clearImage() {
        fileInput.value = "";
        cameraInput.value = "";
        previewImage.src = "#";
        previewContainer.style.display = 'none';
        submitSection.style.display = 'none';
    }
</script>
"""

VIEW_PHOTO_TEMPLATE = """
    <h2>Photo for {{ id }}</h2>
    <img src="{{ url_for('get_file', filename=filename) }}" width="300"><br><br>
    <a href="{{ url_for('photo', id=id) }}">Refresh</a>
"""

@app.route('/photo/<id>')
def photo(id):
    filename = f"{id}.jpg"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if os.path.exists(filepath):
        # If photo exists, show it
        return render_template_string(VIEW_PHOTO_TEMPLATE, id=id, filename=filename)
    else:
        # If not, show upload form
        return render_template_string(UPLOAD_FORM_TEMPLATE, id=id)

@app.route('/upload/<id>', methods=['POST'])
def upload(id):
    if 'photo' not in request.files:
        return "No photo uploaded.", 400

    photo = request.files['photo']
    if photo.filename == '':
        return "No selected file.", 400

    if photo:
        filename = f"{id}.jpg"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        photo.save(save_path)
        return redirect(url_for('photo', id=id))

@app.route('/uploads/<filename>')
def get_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

x