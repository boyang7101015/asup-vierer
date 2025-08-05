from flask import Flask, request, render_template, jsonify, session
from werkzeug.utils import secure_filename
import os
import py7zr
import gzip
import pandas as pd
from lxml import etree
import re
import uuid

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_default_secret_key')

BASE_UPLOAD_FOLDER = 'uploads'
BASE_EXTRACT_FOLDER = 'extracted'
ALLOWED_EXTENSIONS = {'7z', 'txt', 'xml', 'csv', 'gz'}
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB

app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BASE_EXTRACT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_filename(filename):
    return secure_filename(filename)

def get_user_folders():
    session_id = session.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
    user_upload_folder = os.path.join(BASE_UPLOAD_FOLDER, session_id)
    user_extract_folder = os.path.join(BASE_EXTRACT_FOLDER, session_id)
    os.makedirs(user_upload_folder, exist_ok=True)
    os.makedirs(user_extract_folder, exist_ok=True)
    return user_upload_folder, user_extract_folder

def clear_folder(folder_path):
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                clear_folder(file_path)
                os.rmdir(file_path)

def parse_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().replace("\n", "<br>")
        return f"<pre>{content}</pre>"
    except Exception as e:
        return f"<p class='text-danger'>讀取失敗: {str(e)}</p>"

def parse_xml(file_path):
    try:
        tree = etree.parse(file_path)
        root = tree.getroot()
        namespaces = {
            'default': 'http://asup_search.netapp.com/ns/T_VIF/1.0',
            'asup': 'http://asup_search.netapp.com/ns/ASUP/1.1'
        }
        rows = []
        for row in root.findall('asup:ROW', namespaces):
            row_data = {}
            for child in row:
                tag = etree.QName(child).localname
                if tag == 'list':
                    list_items = [li.text.strip() for li in child.findall('asup:li', namespaces) if li.text]
                    row_data[tag] = ', '.join(list_items)
                elif tag in ['services', 'data_protocol', 'failover_targets']:
                    list_items = [li.text.strip() for li in child.findall('asup:list/asup:li', namespaces) if li.text]
                    row_data[tag] = ', '.join(list_items)
                else:
                    row_data[tag] = child.text.strip() if child.text else ''
            rows.append(row_data)
        df = pd.DataFrame(rows)
        return df.to_html(classes="table table-bordered table-striped", index=False, escape=False)
    except Exception as e:
        return f"<p class='text-danger'>解析失敗: {str(e)}</p>"

def parse_sysconfig(file_path):
    result = {"node_name": "未知", "serial_number": "未知", "module_name": "未知", "disk_failed": []}
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.readlines()
            node_match = re.search(r"System Serial Number: \S+ \((.*?)\)", ''.join(content))
            serial_match = re.search(r"System Serial Number: (\S+)", ''.join(content))
            module_match = re.search(r"Model Name:\s+(\S+)", ''.join(content))
            result["node_name"] = node_match.group(1) if node_match else "未知"
            result["serial_number"] = serial_match.group(1) if serial_match else "未知"
            result["module_name"] = module_match.group(1) if module_match else "未知"

            disk_failed_info = {}
            for line in content:
                if "Failed" in line:
                    match = re.search(r"\(([^)]+)\)", line)
                    if match:
                        serial_number = match.group(1)
                        if serial_number not in disk_failed_info:
                            disk_failed_info[serial_number] = line.strip()
            result["disk_failed"] = list(disk_failed_info.values())
    except Exception as e:
        print(f"Error parsing SYSCONFIG-A.txt: {e}")
    return result

def parse_cluster_info(file_path):
    try:
        tree = etree.parse(file_path)
        root = tree.getroot()
        cluster_names = {elem.text for elem in root.findall(".//{*}cluster-name") if elem.text}
        return ", ".join(cluster_names) if cluster_names else "未知"
    except Exception as e:
        print(f"Error parsing CLUSTER-INFO.xml: {e}")
        return "未知"

def parse_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        return df.to_html(classes="table table-bordered table-striped", index=False)
    except Exception as e:
        return f"<p class='text-danger'>解析失敗: {str(e)}</p>"

def parse_gz(file_path):
    try:
        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
            content = f.read().replace("\n", "<br>")
        return f"<pre>{content}</pre>"
    except Exception as e:
        return f"<p class='text-danger'>解壓失敗: {str(e)}</p>"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    user_upload_folder, user_extract_folder = get_user_folders()
    clear_folder(user_upload_folder)
    clear_folder(user_extract_folder)

    if "file" not in request.files:
        return jsonify({"error": "未上傳檔案"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "檔案名稱空白"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "只允許 .7z 檔案"}), 400

    filename = sanitize_filename(file.filename)
    save_path = os.path.join(user_upload_folder, filename)
    file.save(save_path)
    session["uploaded_file_path"] = save_path

    return jsonify({"success": True, "message": "檔案上傳成功，請開始解壓縮", "file_name": filename})

@app.route("/extract", methods=["POST"])
def extract():
    user_extract_folder = get_user_folders()[1]
    upload_path = session.get("uploaded_file_path")
    if not upload_path or not os.path.exists(upload_path):
        return jsonify({"error": "找不到已上傳檔案，請重新上傳"}), 400

    try:
        with py7zr.SevenZipFile(upload_path, mode='r') as archive:
            archive.extractall(path=user_extract_folder)

        sysconfig_data = None
        cluster_name = "未知"
        for root, _, files in os.walk(user_extract_folder):
            for f in files:
                full_path = os.path.join(root, f)
                if f == "SYSCONFIG-A.txt":
                    sysconfig_data = parse_sysconfig(full_path)
                elif f == "CLUSTER-INFO.xml":
                    cluster_name = parse_cluster_info(full_path)

        extracted_files = []
        for root, _, files in os.walk(user_extract_folder):
            for f in files:
                rel_path = os.path.relpath(os.path.join(root, f), user_extract_folder)
                extracted_files.append(rel_path)

        return jsonify({
            "success": True,
            "files": extracted_files,
            "cluster_name": cluster_name,
            "sysconfig_data": sysconfig_data,
            "disk_failed": sysconfig_data.get("disk_failed") if sysconfig_data else []
        })
    except Exception as e:
        return jsonify({"error": f"解壓縮失敗: {str(e)}"}), 500

@app.route("/view-file", methods=["GET"])
def view_file():
    user_extract_folder = get_user_folders()[1]
    file_name = request.args.get("file")
    if not file_name:
        return jsonify({"content": "未指定文件"}), 400

    sanitized_name = sanitize_filename(file_name)
    file_path = os.path.join(user_extract_folder, sanitized_name)

    if not os.path.exists(file_path):
        # 嘗試遍歷找檔案
        found = False
        for root, _, files in os.walk(user_extract_folder):
            if sanitized_name in files:
                file_path = os.path.join(root, sanitized_name)
                found = True
                break
        if not found:
            return jsonify({"content": "文件不存在"}), 404

    ext = file_name.rsplit('.', 1)[1].lower()
    if ext == "txt":
        content = parse_txt(file_path)
    elif ext == "xml":
        content = parse_xml(file_path)
    elif ext == "csv":
        content = parse_csv(file_path)
    elif ext == "gz":
        content = parse_gz(file_path)
    else:
        content = "不支援的文件格式"

    return jsonify({"content": content})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)

