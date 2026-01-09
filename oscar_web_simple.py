#!/usr/bin/env python3
"""
OSCAR NetCDF to GRIB2 Simple Web Converter
Fixed temporary-file handling for production use (Fly.io safe)
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

                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = outputName;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);

                    status.textContent =
                        'Success! Downloaded: ' + outputName + ' (' + blob.size + ' bytes)';
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
        ds = xr.open_dataset(input_path)

        u_data = ds['u'].values[0, :, :].T
        v_data = ds['v'].values[0, :, :].T
        lats = ds['lat'].values
        lons = ds['lon'].values
        time = ds['time'].values[0]

        fill_value = ds['u'].attrs.get('_FillValue', -999.0)
        u_data = np.where(u_data == fill_value, np.nan, u_data)
        v_data = np.where(v_data == fill_value, np.nan, v_data)

        if isinstance(time, datetime):
            year, month, day = time.year, time.month, time.day
        else:
            date_str = str(np.datetime64(time, 'D'))
            year = int(date_str[:4])
            month = int(date_str[5:7])
            day = int(date_str[8:10])

        with open(output_path, 'wb') as f:
            self._write_message(f, u_data, lats, lons, year, month, day, param=2)
            self._write_message(f, v_data, lats, lons, year, month, day, param=3)

    def _write_message(self, f, data, lats, lons, year, month, day, param):
        gid = eccodes.codes_grib_new_from_samples('regular_ll_sfc_grib2')

        try:
            eccodes.codes_set(gid, 'Ni', len(lons))
