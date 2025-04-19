# Get models
from ttslab.utils.storage import list_models, get_model_dir
from flask import Flask, render_template, jsonify, request, send_file, Response, stream_with_context
import os, sys
import importlib.util
import json
import uuid
import threading
import queue
import io
import contextlib
import time
import traceback
import tempfile

# Create Flask app
app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
)

# Global state for tasks
tasks = {}
tasks_lock = threading.Lock()
_log_sentinel = object() # Sentinel to signal end of logs

# Global state for models
models = []
imported_models = {}

# - Setup models -
def initialize_models():
    """Initialize models - call this within a Flask application context"""
    global models, imported_models

models = list_models()
imported_models = {}

for model_name in models:
    model_path = os.path.join(get_model_dir(), model_name)
    init_file = os.path.join(model_path, "__init__.py")
    
    if os.path.exists(init_file):
        try:
            spec = importlib.util.spec_from_file_location(f"ttslab.models.{model_name}", init_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"ttslab.models.{model_name}"] = module
                spec.loader.exec_module(module)
                if hasattr(module, 'TTSLabModel'):
                    imported_models[model_name] = module.TTSLabModel
                else:
                    print(f"Warning: No TTSLabModel class found in {model_name}")
            else:
                print(f"Warning: Could not create spec for {model_name}")
        except Exception as e:
            print(f"Error importing model package {model_name}: {e}")
            traceback.print_exc()

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/models")
def list_models_api():
    """Lists available model packages."""
    model_packages = list_models()  # Call within request context
    
    if not model_packages:
        return jsonify({
            "models": [],
            "installation_info": {
                "message": "No models found. Please install models using the TTSLab CLI.",
                "command": "ttslab install <model-name>",
            }
        })
    return jsonify({"models": model_packages})

@app.route("/api/manifest/<model_name>")
def get_manifest(model_name):
    model_path = os.path.join(get_model_dir(), model_name)
    manifest_file = os.path.join(model_path, "manifest.json")
    
    if os.path.exists(manifest_file):
        try:
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
            return jsonify(manifest)
        except Exception as e:
            return jsonify({"error": f"Failed to load manifest: {str(e)}"}), 500
    else:
        return jsonify({"name": model_name}), 404

@app.route("/api/synthesize", methods=["POST"])
def synthesize():
    from flask import request, send_file
    import tempfile
    import os
    
    # Get form data
    text = request.form.get("text")
    model_id = request.form.get("model_id")
    additional_args_json = request.form.get("additional_args")
    
    # Check if required parameters are provided
    if not text or not model_id:
        return jsonify({"error": "Missing required parameters"}), 400
    
    # Get reference audio if provided
    reference_audio = None
    if "reference_audio" in request.files:
        file = request.files["reference_audio"]
        if file.filename:
            # Save the uploaded file to a temporary location
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, file.filename)
            file.save(temp_path)
            reference_audio = temp_path
    
    # Find the model that can handle this model_id
    model_instance = None
    for model_name, module in imported_models.items():
        if hasattr(module, "TTSLabModel"):
            model_class = module.TTSLabModel
            # Check if this model supports the requested model_id
            if model_id in [m_id["id"] for m_id in model_class.models if isinstance(m_id, dict) and "id" in m_id]:
                model_instance = model_class()
                break
    
    if not model_instance:
        return jsonify({"error": f"No model found that supports {model_id}"}), 404
    
    # Create a temporary file for the output
    output_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    output_path = output_file.name
    output_file.close()
    
    try:
        # Define a progress callback (optional)
        def progress_callback(percent):
            # This could be used with a websocket to report progress
            pass
        
        # Parse additional args
        additional_args = {}
        if additional_args_json:
            try:
                additional_args = json.loads(additional_args_json)
                if not isinstance(additional_args, dict):
                    raise ValueError("additional_args must be a JSON object")
            except (json.JSONDecodeError, ValueError) as e:
                return jsonify({"error": f"Invalid additional_args format: {e}"}), 400
        
        # Call the model
        try:
            model_instance(
                model_id=model_id,
                text=text,
                reference_audio=reference_audio,
                speaker_id=None,  # Not using speaker_id for now
                additional_args=additional_args,
                output_file=output_path
            )
        except Exception as model_error:
            return jsonify({"error": f"Model inference failed: {str(model_error)}"}), 500
        
        # Check if file was created and has content
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return jsonify({"error": "Failed to generate audio - empty or missing file"}), 500
        
        # Return the audio file with explicit cache control
        response = send_file(
            output_path,
            mimetype="audio/wav",
            as_attachment=True,
            download_name="synthesized_speech.wav"
        )
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["Accept-Ranges"] = "bytes"
        return response
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in /api/synthesize: {str(e)}\n{error_trace}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        # Clean up temporary files
        if reference_audio and os.path.exists(reference_audio):
            os.unlink(reference_audio)
        if os.path.exists(output_path):
            os.unlink(output_path)


@app.route("/api/models/<model_name>")
def model(model_name):
    if model_name not in imported_models:
        return jsonify({"error": "Model not found"}), 404
    model_instance = imported_models[model_name].TTSLabModel
    
    # Handle both old dict and new list format
    if hasattr(model_instance, 'models'):
        models = model_instance.models
        if isinstance(models, dict):
            # Convert dict to list with key as a property
            model_list = []
            for key, value in models.items():
                model_data = value.copy() if isinstance(value, dict) else {"id": value}
                model_data["key"] = key
                model_list.append(model_data)
            return jsonify(model_list)
        elif isinstance(models, list):
            # Already in the correct format
            return jsonify(models)
        else:
            return jsonify([{"id": model_name, "error": "Invalid model format"}])
    else:
        return jsonify([{"id": model_name, "name": model_name}])

# --- Task Management Setup ---
tasks = {}
tasks_lock = threading.Lock()
_log_sentinel = object() # Sentinel to signal end of logs

# --- Model Loading Logic ---
# Load model package names
model_packages = list_models()

# Import the TTSLabModel class from each package
for package_name in model_packages:
    model_path = os.path.join(get_model_dir(), package_name)
    init_file = os.path.join(model_path, "__init__.py")
    
    if os.path.exists(init_file):
        try:
            spec = importlib.util.spec_from_file_location(f"ttslab.models.{package_name}", init_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                # Add to sys.modules BEFORE exec_module to handle relative imports within the module
                sys.modules[f"ttslab.models.{package_name}"] = module 
                spec.loader.exec_module(module)
                if hasattr(module, 'TTSLabModel'):
                    imported_models[package_name] = module.TTSLabModel
                else:
                    print(f"Warning: No TTSLabModel class found in {package_name}")
            else:
                 print(f"Warning: Could not create spec for {package_name}")
        except Exception as e:
            print(f"Error importing model package {package_name}: {e}")
            traceback.print_exc()


# --- Log Capturing Utility ---
class QueueIO(io.TextIOBase):
    """ A file-like object that writes to a queue. """
    def __init__(self, q):
        self.queue = q

    def write(self, s):
        if s.strip():  # Only queue non-empty strings
            self.queue.put(s)
        return len(s)
    
    def flush(self):
        # Required for some print statements that flush
        pass

@contextlib.contextmanager
def capture_logs(log_queue):
    """Context manager to capture stdout and stderr in a queue."""
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # Create a new queue writer that will send to the log queue
    capture_stream = QueueIO(log_queue)
    
    # Redirect stdout and stderr
    sys.stdout = capture_stream
    sys.stderr = capture_stream
    
    try:
        yield
    finally:
        # Restore original stdout and stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        # Signal that logging from this capture is complete
        log_queue.put(_log_sentinel)

# --- Background Synthesis Task ---
def run_synthesis_task(task_id, log_queue, model_instance, model_id, text, reference_audio_path, additional_args):
    """ The function that runs in a separate thread to perform synthesis. """
    output_path = None
    task_status = 'running'
    error_message = None
    
    # Create a temporary file for the output *within the task*
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as output_file:
            output_path = output_file.name
    except Exception as e:
         error_message = f"Failed to create temporary output file: {e}"
         task_status = 'error'
         # Update task immediately if temp file fails
         with tasks_lock:
             tasks[task_id].update({
                 'status': task_status,
                 'error_message': error_message,
             })
         log_queue.put(f"ERROR: {error_message}")
         log_queue.put(_log_sentinel) # Signal completion even on error
         # Clean up reference audio if it exists
         if reference_audio_path and os.path.exists(reference_audio_path):
             try:
                 os.unlink(reference_audio_path)
             except OSError as unlink_err:
                 print(f"Warning: Could not delete temp reference audio {reference_audio_path}: {unlink_err}")
         return # Exit task


    try:
        # Capture logs during the model call
        log_queue.put(f"Starting synthesis for task {task_id}...")
        log_queue.put(f"  Model ID: {model_id}")
        log_queue.put(f"  Output Path: {output_path}")
        with capture_logs(log_queue):
            # Call the model's __call__ method
            model_instance(
                model_id=model_id,
                text=text,
                reference_audio=reference_audio_path,
                speaker_id=None, # Assuming speaker_id is not used for now
                additional_args=additional_args,
                output_file=output_path 
            )
        
        # Check if the output file was actually created and has content
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
             raise RuntimeError("Model execution finished, but output file is missing or empty.")

        log_queue.put(f"Synthesis completed successfully. Output: {output_path}")
        task_status = 'complete'

    except Exception as e:
        error_message = f"Model inference failed: {str(e)}"
        task_status = 'error'
        # Ensure log sentinel is put even if capture_logs context exits early due to error
        if sys.stdout != original_stdout: # Check if redirection is still active
             log_queue.put(_log_sentinel) 
             sys.stdout = original_stdout # Restore stdout/stderr just in case
             sys.stderr = original_stderr
        else: # Put sentinel if capture_logs already exited
             log_queue.put(_log_sentinel) 
        
        log_queue.put(f"ERROR: {error_message}")
        traceback.print_exc(file=QueueIO(log_queue)) # Send traceback to logs

    finally:
        # Update task status in the shared dictionary
        with tasks_lock:
            if task_id in tasks: # Check if task hasn't been cleaned up already
                tasks[task_id].update({
                    'status': task_status,
                    'audio_path': output_path if task_status == 'complete' else None,
                    'error_message': error_message,
                })
            else:
                 print(f"Warning: Task {task_id} not found during final update.")
        
        # Clean up reference audio file if it was created
        if reference_audio_path and os.path.exists(reference_audio_path):
            try:
                os.unlink(reference_audio_path)
                log_queue.put(f"Cleaned up temporary reference audio: {reference_audio_path}")
            except OSError as unlink_err:
                print(f"Warning: Could not delete temp reference audio {reference_audio_path}: {unlink_err}")
                log_queue.put(f"Warning: Could not delete temp reference audio {reference_audio_path}: {unlink_err}")
        
        # Clean up the output file ONLY if there was an error (otherwise served by /api/audio)
        if task_status == 'error' and output_path and os.path.exists(output_path):
             try:
                 os.unlink(output_path)
                 log_queue.put(f"Cleaned up temporary output file due to error: {output_path}")
             except OSError as unlink_err:
                 print(f"Warning: Could not delete temp output audio {output_path} after error: {unlink_err}")
                 log_queue.put(f"Warning: Could not delete temp output audio {output_path} after error: {unlink_err}")
                 
        # Signal completion of the task itself (logs might have already finished via sentinel)
        log_queue.put(_log_sentinel) # Add extra sentinel to ensure stream endpoint exits


# --- Flask App Setup ---
app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
)

# --- API Endpoints ---

@app.route("/")
def index():
    """Serves the main HTML page."""
    return render_template("index.html")

@app.route("/api/models")
def list_models_api():
    """Lists available model packages."""
    if not model_packages:
        return jsonify({
            "models": [],
            "installation_info": {
                "message": "No TTS model packages found. Please install models using the TTSLab CLI.",
                "command": "ttslab install <model-package-name>",
            }
        })
    # Return the list of package names ['f5_tts', ...]
    return jsonify({"models": model_packages})

@app.route("/api/manifest/<package_name>")
def get_manifest(package_name):
    """Gets the manifest JSON for a given model package."""
    model_path = os.path.join(get_model_dir(), package_name)
    manifest_file = os.path.join(model_path, "manifest.json")
    
    if os.path.exists(manifest_file):
        try:
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
            return jsonify(manifest)
        except Exception as e:
            print(f"Error reading manifest for {package_name}: {e}")
            return jsonify({"error": f"Failed to load manifest: {str(e)}"}), 500
    else:
        # Return minimal info if manifest doesn't exist
        return jsonify({"name": package_name}), 404 

@app.route("/api/models/<package_name>")
def get_package_models(package_name):
    """Gets the list of specific models within a package."""
    if package_name not in imported_models:
        return jsonify({"error": f"Model package '{package_name}' not found or failed to load."}), 404
    
    model_class = imported_models[package_name]
    
    if hasattr(model_class, 'models') and isinstance(model_class.models, list):
        # Assuming models are defined as a list of dicts in the class
        return jsonify(model_class.models)
    else:
        print(f"Warning: 'models' attribute not found or not a list in {package_name}.TTSLabModel")
        # Return a default representation or error
        return jsonify([{"id": package_name, "name": f"{package_name} (default)", "description": "Model details not available."}])


@app.route("/api/synthesize", methods=["POST"])
def synthesize_start():
    """Starts the synthesis process in a background thread and returns a task ID."""
    text = request.form.get("text")
    model_id = request.form.get("model_id") # This is the specific model ID (e.g., 'f5-tts-v1')
    additional_args_json = request.form.get("additional_args")
    
    if not text or not model_id:
        return jsonify({"error": "Missing required parameters (text or model_id)"}), 400

    # Find the correct model package and instance based on the sub-model ID
    found_package_name = None
    model_instance = None
    for pkg_name, model_cls in imported_models.items():
        if hasattr(model_cls, 'models') and isinstance(model_cls.models, list):
             for model_def in model_cls.models:
                 if isinstance(model_def, dict) and model_def.get('id') == model_id:
                     try:
                         model_instance = model_cls() # Instantiate the class
                         found_package_name = pkg_name
                         break
                     except Exception as e:
                          print(f"Error instantiating model class {pkg_name}: {e}")
                          return jsonify({"error": f"Failed to load model '{model_id}': {e}"}), 500
             if model_instance:
                 break # Exit outer loop once instance is created

    if not model_instance:
        return jsonify({"error": f"No loaded model package supports the specific model ID '{model_id}'"}), 404

    # Handle reference audio upload
    reference_audio_path = None
    temp_audio_dir = None # Keep track of temp dir for potential cleanup
    if "reference_audio" in request.files:
        file = request.files["reference_audio"]
        if file and file.filename:
            try:
                temp_audio_dir = tempfile.mkdtemp()
                # Sanitize filename slightly (replace spaces, etc.) - more robust needed for prod
                safe_filename = file.filename.replace(" ", "_") 
                reference_audio_path = os.path.join(temp_audio_dir, safe_filename)
                file.save(reference_audio_path)
                print(f"Saved reference audio to: {reference_audio_path}")
            except Exception as e:
                print(f"Error saving reference audio: {e}")
                # Clean up directory if creation succeeded but save failed
                if temp_audio_dir and os.path.exists(temp_audio_dir):
                     try: 
                         os.rmdir(temp_audio_dir) 
                     except OSError: pass # Ignore error if dir not empty/already gone
                return jsonify({"error": f"Failed to save reference audio: {e}"}), 500

    # Parse additional args
    additional_args = {}
    if additional_args_json:
        try:
            additional_args = json.loads(additional_args_json)
            if not isinstance(additional_args, dict):
                raise ValueError("additional_args must be a JSON object")
        except (json.JSONDecodeError, ValueError) as e:
             # Cleanup uploaded audio if args parsing fails
             if reference_audio_path and os.path.exists(reference_audio_path):
                 try: os.unlink(reference_audio_path) 
                 except OSError: pass
             if temp_audio_dir and os.path.exists(temp_audio_dir):
                 try: os.rmdir(temp_audio_dir) 
                 except OSError: pass
             return jsonify({"error": f"Invalid additional_args format: {e}"}), 400

    # --- Start Background Task ---
    task_id = str(uuid.uuid4())
    log_queue = queue.Queue()

    thread = threading.Thread(
        target=run_synthesis_task,
        args=(
            task_id, 
            log_queue, 
            model_instance, 
            model_id, 
            text, 
            reference_audio_path, # Pass the path
            additional_args
        )
    )

    with tasks_lock:
        tasks[task_id] = {
            'queue': log_queue,
            'thread': thread,
            'status': 'starting',
            'audio_path': None,
            'error_message': None,
             # Store temp dir path if created, to aid cleanup if needed later
            'temp_audio_dir': temp_audio_dir 
        }
    
    thread.start()
    print(f"Started synthesis task {task_id} for model {model_id}")

    # Return task ID so frontend can connect to the stream
    return jsonify({"task_id": task_id})


@app.route('/stream/<task_id>')
def stream_logs(task_id):
    """Streams logs for a given task ID using Server-Sent Events."""
    
    # Get the queue for this task - need function scope copy for generator
    log_queue = None
    with tasks_lock:
        task_info = tasks.get(task_id)
        if task_info:
            log_queue = task_info['queue']
        
    if not log_queue:
        # Task might be invalid or cleaned up already
        def immediate_error_stream():
             yield f"event: error\ndata: {json.dumps({'message': 'Invalid or expired task ID.'})}\n\n"
        return Response(stream_with_context(immediate_error_stream()), mimetype='text/event-stream')

    def generate():
        sentinel_count = 0
        max_sentinels = 2 # Expect one from stdout/stderr context, one from task end
        while sentinel_count < max_sentinels:
            try:
                # Wait for a log message with a timeout
                log_entry = log_queue.get(timeout=5.0) 

                if log_entry is _log_sentinel:
                    sentinel_count += 1
                    print(f"Task {task_id}: Received log sentinel ({sentinel_count}/{max_sentinels})")
                    continue # Don't send sentinel to client

                # Format log entry for SSE
                # Split by newlines and send each line as a separate data line
                # This ensures proper multi-line formatting in the client
                if '\n' in str(log_entry):
                    output_lines = []
                    for line in str(log_entry).split('\n'):
                        if line.strip():  # Only include non-empty lines
                            output_lines.append(f"data: {line}")
                    if output_lines:
                        yield '\n'.join(output_lines) + '\n\n'
                else:
                    # For single-line entries
                    yield f"data: {str(log_entry)}\n\n"

            except queue.Empty:
                # Timeout occurred, send keepalive comment
                yield ": keepalive\n\n"
            except Exception as e:
                 # Log error on server, inform client
                 print(f"Error in stream generator for task {task_id}: {e}")
                 yield f"event: error\ndata: {json.dumps({'message': f'Streaming error: {e}'})}\n\n"
                 break # Stop streaming on internal error
        
        # --- Loop finished (all sentinels received or error occurred) ---
        print(f"Log stream loop finished for task {task_id}.")
        
        # Check final task status
        final_status = 'unknown'
        final_audio_path = None
        final_error_message = 'Task finished but final status unknown.'
        
        with tasks_lock:
            task_info = tasks.get(task_id)
            if task_info:
                final_status = task_info.get('status', 'unknown')
                final_audio_path = task_info.get('audio_path')
                final_error_message = task_info.get('error_message')
        
        # Send final event based on status
        if final_status == 'complete' and final_audio_path:
            try:
                 # Generate direct URL instead of using url_for
                 audio_url = f"/api/audio/{task_id}"
                 print(f"Task {task_id} complete. Sending audio URL: {audio_url}")
                 yield f"event: complete\ndata: {json.dumps({'audio_url': audio_url})}\n\n"
            except Exception as url_err:
                 print(f"Error generating audio URL for task {task_id}: {url_err}")
                 yield f"event: error\ndata: {json.dumps({'message': f'Task complete but failed to create audio URL: {url_err}'})}\n\n"
        elif final_status == 'error':
             print(f"Task {task_id} failed. Sending error: {final_error_message}")
             yield f"event: error\ndata: {json.dumps({'message': final_error_message or 'Unknown error during synthesis.'})}\n\n"
        else:
             # Should ideally not happen if logic is correct, but handle it
             print(f"Task {task_id} finished with unexpected status: {final_status}. Path: {final_audio_path}")
             yield f"event: error\ndata: {json.dumps({'message': f'Task ended with unclear status: {final_status}'})}\n\n"

        print(f"SSE stream closing for task {task_id}.")

    # Return the streaming response
    resp = Response(stream_with_context(generate()), mimetype='text/event-stream')
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no' # Useful for Nginx buffering issues
    return resp


@app.route('/api/audio/<task_id>')
def get_audio(task_id):
    """Serves the generated audio file and cleans up."""
    audio_path = None
    temp_audio_dir = None
    
    with tasks_lock:
        task_info = tasks.get(task_id)
        if task_info and task_info.get('status') == 'complete':
            audio_path = task_info.get('audio_path')
            temp_audio_dir = task_info.get('temp_audio_dir') # Get potential ref audio dir

    if not audio_path or not os.path.exists(audio_path):
        # Cleanup task entry if audio is missing/invalid
        with tasks_lock:
            if task_id in tasks:
                del tasks[task_id] 
        return jsonify({"error": "Audio file not found or task is invalid/incomplete."}), 404

    try:
        # Use a callback to delete the file after it's sent
        def cleanup_files():
             try:
                 if audio_path and os.path.exists(audio_path):
                     os.unlink(audio_path)
                     print(f"Cleaned up audio file: {audio_path}")
                 # Also clean up the reference audio directory if it exists
                 if temp_audio_dir and os.path.exists(temp_audio_dir):
                     # We only created the dir, reference file inside was deleted by task
                     try:
                          os.rmdir(temp_audio_dir) 
                          print(f"Cleaned up temp ref audio dir: {temp_audio_dir}")
                     except OSError as rmdir_err:
                          print(f"Warning: Could not remove temp ref audio dir {temp_audio_dir}: {rmdir_err}")
                          
                 # Remove task from dictionary after cleanup
                 with tasks_lock:
                     if task_id in tasks:
                         del tasks[task_id]
                         print(f"Removed task entry {task_id}")
                         
             except Exception as e:
                 print(f"Error during cleanup for task {task_id}: {e}")

        response = send_file(
            audio_path,
            mimetype="audio/wav",
            as_attachment=False, # Play inline
            download_name=f"tts_output_{task_id}.wav"
        )
        # Register the cleanup function to run after the request context ends
        response.call_on_close(cleanup_files) 
        
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
        
    except Exception as e:
        print(f"Error sending file for task {task_id}: {e}")
        # Attempt cleanup even if send_file fails
        cleanup_files()
        return jsonify({"error": f"Failed to send audio file: {str(e)}"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    # Initialize models within app context
    with app.app_context():
        initialize_models()
    
    # Run with threading enabled for background tasks
    app.run(debug=True, threaded=True, host='0.0.0.0', port=5000)