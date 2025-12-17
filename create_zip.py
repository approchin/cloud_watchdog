import os
import zipfile

def zip_project(output_filename):
    # Get the current directory (project root)
    project_root = os.getcwd()
    
    # Define directories/files to exclude
    exclude_dirs = {'.venv', '__pycache__', '.git', '.pytest_cache', 'logs', 'state'}
    exclude_files = {output_filename, '.DS_Store'}

    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_root):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file in exclude_files:
                    continue
                
                file_path = os.path.join(root, file)
                # Create a relative path for the archive
                arcname = os.path.relpath(file_path, project_root)
                
                # Add file to zip
                print(f"Adding {arcname}")
                zipf.write(file_path, arcname)

if __name__ == "__main__":
    zip_project("cloud-watchdog.zip")
    print("Project successfully zipped to cloud-watchdog.zip")