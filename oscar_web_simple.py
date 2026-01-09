#!/usr/bin/env python3
"""
OSCAR NetCDF to GRIB2 Simple Web Converter
A simplified version that's easier to debug
"""

from flask import Flask, request, send_file, render_template_string
import os
import tempfile
import xarray as xr
import numpy as np
import eccodes
from datetime import datetime

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

# Simple HTML page
HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>OSCAR Converter</title>
    <style>
        body { font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; }
        h1 { color: #333; }
        .upload-area { border: 2px dashed #ccc; padding: 40px; text-align: center; margin: 20px 0; }
        .upload-area:hover { background: #f5f5f5; }
        button { background: #4CAF50; color: white; padding: 10px 20px; border: none; cursor: pointer; font-size: 16px; }
        button:hover { background: #45a049; }
        #status { margin-top: 20px; padding: 10px; }
        .success { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <h1>OSCAR NetCDF to GRIB2 Converter</h1>
    
    <div class="upload-area" onclick="document.getElementById('fileInput').click()">
        <p>Click to select OSCAR NetCDF file (.nc or .nc4)</p>
    </div>
    
    <input type="file" id="fileInput" accept=".nc,.nc4" style="display:none" onchange="uploadFile()">
    
    <div id="status"></div>
    
    <script>
        async function uploadFile() {
            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];
            const status = document.getElementById('status');
            
            if (!file) return;
            
            status.textContent = 'Converting ' + file.name + '...';
            status.className = '';
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const response = await fetch('/convert', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const blob = await response.blob();
                    const outputName = file.name.replace(/\\.nc4?$/, '.grb2');
                    
                    // Trigger download
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = outputName;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                    
                    status.textContent = 'Success! Downloaded: ' + outputName + ' (' + blob.size + ' bytes)';
                    status.className = 'success';
                } else {
                    const error = await response.text();
                    status.textContent = 'Error: ' + error;
                    status.className = 'error';
                }
            } catch (error) {
                status.textContent = 'Error: ' + error.message;
                status.className = 'error';
            }
        }
    </script>
</body>
</html>
'''


class OSCARConverter:
    """Convert OSCAR NetCDF to GRIB2"""
    
    def convert(self, input_path, output_path):
        """Convert NetCDF file to GRIB2"""
        # Read NetCDF
        ds = xr.open_dataset(input_path)
        u_data = ds['u'].values[0, :, :].T  # (time, lon, lat) -> (lat, lon)
        v_data = ds['v'].values[0, :, :].T
        lats = ds['lat'].values
        lons = ds['lon'].values
        time = ds['time'].values[0]
        
        # Handle fill values
        fill_value = ds['u'].attrs.get('_FillValue', -999.0)
        u_data = np.where(u_data == fill_value, np.nan, u_data)
        v_data = np.where(v_data == fill_value, np.nan, v_data)
        
        # Extract time
        if isinstance(time, datetime):
            year, month, day = time.year, time.month, time.day
        else:
            date_str = str(np.datetime64(time, 'D'))
            year = int(date_str[:4])
            month = int(date_str[5:7])
            day = int(date_str[8:10])
        
        # Write GRIB2
        with open(output_path, 'wb') as f:
            self._write_message(f, u_data, lats, lons, year, month, day, param=2)
            self._write_message(f, v_data, lats, lons, year, month, day, param=3)
    
    def _write_message(self, f, data, lats, lons, year, month, day, param):
        """Write a GRIB2 message"""
        gid = eccodes.codes_grib_new_from_samples('regular_ll_sfc_grib2')
        
        try:
            eccodes.codes_set(gid, 'Ni', len(lons))
            eccodes.codes_set(gid, 'Nj', len(lats))
            eccodes.codes_set(gid, 'latitudeOfFirstGridPointInDegrees', float(lats[0]))
            eccodes.codes_set(gid, 'latitudeOfLastGridPointInDegrees', float(lats[-1]))
            eccodes.codes_set(gid, 'longitudeOfFirstGridPointInDegrees', float(lons[0]))
            eccodes.codes_set(gid, 'longitudeOfLastGridPointInDegrees', float(lons[-1]))
            eccodes.codes_set(gid, 'iDirectionIncrementInDegrees', abs(float(lons[1] - lons[0])))
            eccodes.codes_set(gid, 'jDirectionIncrementInDegrees', abs(float(lats[1] - lats[0])))
            eccodes.codes_set(gid, 'dataDate', int(f'{year:04d}{month:02d}{day:02d}'))
            eccodes.codes_set(gid, 'dataTime', 0)
            eccodes.codes_set(gid, 'discipline', 10)  # Oceanographic
            eccodes.codes_set(gid, 'parameterCategory', 1)  # Currents
            eccodes.codes_set(gid, 'parameterNumber', param)  # 2=u, 3=v
            eccodes.codes_set(gid, 'typeOfLevel', 'oceanSurface')
            eccodes.codes_set(gid, 'level', 0)
            
            # Set data
            data_flat = data.flatten()
            if not np.all(~np.isnan(data_flat)):
                eccodes.codes_set(gid, 'bitmapPresent', 1)
                data_flat = np.where(np.isnan(data_flat), 0, data_flat)
            
            eccodes.codes_set_values(gid, data_flat.tolist())
            eccodes.codes_write(gid, f)
        finally:
            eccodes.codes_release(gid)


converter = OSCARConverter()


@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/convert', methods=['POST'])
def convert():
    """Convert uploaded file"""
    temp_input = None
    temp_output = None
    
    try:
        # Get uploaded file
        if 'file' not in request.files:
            return 'No file uploaded', 400
        
        file = request.files['file']
        if not file.filename:
            return 'No file selected', 400
        
        print(f"\n{'='*60}")
        print(f"Converting: {file.filename}")
        
        # Save uploaded file
        temp_input = tempfile.mktemp(suffix='.nc4')
        file.save(temp_input)
        input_size = os.path.getsize(temp_input)
        print(f"Input size: {input_size} bytes")
        
        # Convert
        temp_output = tempfile.mktemp(suffix='.grb2')
        converter.convert(temp_input, temp_output)
        output_size = os.path.getsize(temp_output)
        print(f"Output size: {output_size} bytes")
        
        # Check magic bytes
        with open(temp_output, 'rb') as f:
            magic = f.read(4)
            print(f"Magic bytes: {magic}")
            if magic != b'GRIB':
                return 'Conversion failed: invalid GRIB2 output', 500
        
        # Send file
        output_name = file.filename.replace('.nc4', '.grb2').replace('.nc', '.grb2')
        print(f"Sending: {output_name}")
        print('='*60 + '\n')
        
        return send_file(
            temp_output,
            as_attachment=True,
            download_name=output_name,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return str(e), 500
    
    finally:
        # Cleanup
        if temp_input and os.path.exists(temp_input):
            try:
                os.unlink(temp_input)
            except:
                pass


if __name__ == '__main__':
    import socket
    import webbrowser
    import threading
    import time
    
    # Find available port
    port = 5000
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sock.connect_ex(('127.0.0.1', port)) == 0:
        port = 5001
    sock.close()
    
    print("\n" + "="*60)
    print("OSCAR NetCDF to GRIB2 Converter")
    print("="*60)
    print(f"\nStarting server on port {port}...")
    print(f"\nOpen your browser to: http://localhost:{port}")
    print("\nPress Ctrl+C to stop")
    print("="*60 + "\n")
    
    # Open browser after delay
    def open_browser():
        time.sleep(2)
        webbrowser.open(f'http://localhost:{port}')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    app.run(host='127.0.0.1', port=port, debug=False)
