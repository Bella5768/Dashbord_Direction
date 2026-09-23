/**
 * s3-upload.js
 * Upload files directly to Amazon S3 via a presigned POST, then store the
 * public URL (CloudFront or S3) into the form field.
 * Works with .file-drop wrappers and .lf-dropzone multi-file zones
 * (same HTML contract as the former cloudinary-upload.js).
 */
(function () {
    'use strict';

    var PRESIGN_URL = window.__UPLOAD_PRESIGN_URL__ || '';
    var MAX_SIZE_MB = 20;

    if (!PRESIGN_URL) return;

    function getCsrf() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el && el.value) return el.value;
        return (window.django && window.django.csrf) || '';
    }

    function isAllowedFile(file) {
        var ALLOWED_EXTS = ['pdf','doc','docx','xls','xlsx','ppt','pptx','odt','ods','odp','png','jpg','jpeg','gif','webp','txt','csv','zip'];
        var ext = file.name.split('.').pop().toLowerCase();
        return ALLOWED_EXTS.indexOf(ext) !== -1;
    }

    function requestPresign(filename) {
        return fetch(PRESIGN_URL, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrf()
            },
            body: JSON.stringify({ filename: filename })
        }).then(function (resp) {
            if (!resp.ok) return resp.json().then(function (d) { throw new Error((d && d.error) || 'Erreur presign'); });
            return resp.json();
        });
    }

    function uploadToS3(file, onProgress) {
        return new Promise(function (resolve, reject) {
            if (!isAllowedFile(file)) {
                reject(new Error('Type de fichier non autorise: ' + file.name));
                return;
            }
            if (file.size > MAX_SIZE_MB * 1024 * 1024) {
                reject(new Error('Fichier trop volumineux: ' + file.name + ' (max ' + MAX_SIZE_MB + ' Mo)'));
                return;
            }

            requestPresign(file.name).then(function (presign) {
                var formData = new FormData();
                var fields = presign.fields || {};
                Object.keys(fields).forEach(function (k) {
                    formData.append(k, fields[k]);
                });
                formData.append('file', file);

                var xhr = new XMLHttpRequest();
                xhr.open('POST', presign.url);

                if (onProgress) {
                    xhr.upload.addEventListener('progress', function (e) {
                        if (e.lengthComputable) {
                            onProgress(Math.round((e.loaded / e.total) * 100));
                        }
                    });
                }

                xhr.onload = function () {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        resolve({ url: presign.public_url, name: file.name });
                    } else {
                        var err;
                        try { err = JSON.parse(new XMLSerializer().serializeToString(xhr.responseXML)); } catch (e) { err = null; }
                        reject(new Error('Erreur upload S3' + (err && err.Message ? ': ' + err.Message : '')));
                    }
                };
                xhr.onerror = function () {
                    reject(new Error('Erreur reseau lors de l\'upload'));
                };
                xhr.send(formData);
            }).catch(reject);
        });
    }

    function createProgress(container) {
        var bar = document.createElement('div');
        bar.className = 'cloudinary-progress';
        bar.innerHTML = '<div class="cloudinary-progress-bar"><div class="cloudinary-progress-fill"></div></div><span class="cloudinary-progress-text">0%</span>';
        container.appendChild(bar);
        return {
            setProgress: function (pct) {
                bar.querySelector('.cloudinary-progress-fill').style.width = pct + '%';
                bar.querySelector('.cloudinary-progress-text').textContent = pct + '%';
            },
            remove: function () { bar.remove(); }
        };
    }

    /**
     * Initialize a .file-drop wrapper for S3 upload.
     *
     * Expected HTML structure:
     *   <div class="file-drop" data-field="file">
     *     <input type="hidden" name="file" value="...">   ← Django URLField (existing value)
     *     <input type="file" name="_file_upload" ...>      ← visible file picker
     *     <div class="file-drop-zone">...</div>
     *     <div class="file-drop-selected">...</div>
     *   </div>
     */
    function initSingleUpload(wrapper) {
        var fileInput = wrapper.querySelector('input[type=file]');
        var hiddenField = wrapper.querySelector('input[type=hidden]');
        var nameEl = wrapper.querySelector('.file-drop-name');
        var clearBtn = wrapper.querySelector('.file-drop-clear');
        var dropZone = wrapper.querySelector('.file-drop-zone');
        if (!fileInput || !hiddenField) return;

        var fieldName = hiddenField.name || 'file';

        if (dropZone) {
            dropZone.addEventListener('click', function (e) {
                if (wrapper.classList.contains('is-uploading')) return;
                fileInput.click();
            });
        }

        function handleFiles(files) {
            if (!files || !files[0]) return;
            var file = files[0];
            if (nameEl) nameEl.textContent = file.name;
            wrapper.classList.add('has-file');
            wrapper.classList.add('is-uploading');

            var progress = createProgress(wrapper);

            uploadToS3(file, function (pct) {
                progress.setProgress(pct);
            }).then(function (result) {
                progress.remove();
                wrapper.classList.remove('is-uploading');
                hiddenField.value = result.url;
            }).catch(function (err) {
                progress.remove();
                wrapper.classList.remove('is-uploading');
                wrapper.classList.remove('has-file');
                if (nameEl) nameEl.textContent = '';
                alert('Erreur: ' + err.message);
            });
        }

        fileInput.addEventListener('change', function () {
            handleFiles(this.files);
        });

        if (clearBtn) {
            clearBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                fileInput.value = '';
                hiddenField.value = '';
                wrapper.classList.remove('has-file');
                if (nameEl) nameEl.textContent = '';
            });
        }

        wrapper.addEventListener('dragover', function (e) {
            e.preventDefault();
            this.classList.add('drag-over');
        });
        wrapper.addEventListener('dragleave', function () {
            this.classList.remove('drag-over');
        });
        wrapper.addEventListener('drop', function (e) {
            e.preventDefault();
            this.classList.remove('drag-over');
            handleFiles(e.dataTransfer && e.dataTransfer.files);
        });
    }

    /**
     * Initialize the leave form multi-file dropzone.
     *
     * Expected HTML:
     *   <label class="lf-dropzone">
     *     <div class="lf-dz-icon">...</div>
     *     <div class="lf-dz-title">...</div>
     *     <div class="lf-dz-files" id="lf-dz-files"></div>
     *   </label>
     *   <input type="hidden" name="extra_documents_json" value="[]">
     */
    function initMultiUpload(dzLabel) {
        var hiddenField = document.querySelector('[name=extra_documents_json]');
        if (!hiddenField || !dzLabel) return;

        var chipsContainer = dzLabel.querySelector('.lf-dz-files');
        if (!chipsContainer) {
            chipsContainer = document.createElement('div');
            chipsContainer.className = 'lf-dz-files';
            chipsContainer.id = 'lf-dz-files';
            dzLabel.appendChild(chipsContainer);
        }

        var uploadedFiles = [];
        try { uploadedFiles = JSON.parse(hiddenField.value || '[]'); } catch (e) { uploadedFiles = []; }

        function renderChips() {
            chipsContainer.innerHTML = '';
            uploadedFiles.forEach(function (f, idx) {
                var chip = document.createElement('span');
                chip.className = 'chip';
                chip.textContent = f.name || (f.url || '').split('/').pop() || 'document';
                var removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.className = 'chip-remove';
                removeBtn.innerHTML = '&times;';
                removeBtn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    uploadedFiles.splice(idx, 1);
                    hiddenField.value = JSON.stringify(uploadedFiles);
                    renderChips();
                });
                chip.appendChild(removeBtn);
                chipsContainer.appendChild(chip);
            });
        }

        renderChips();

        function handleFiles(files) {
            if (!files || files.length === 0) return;
            Array.from(files).forEach(function (file) {
                var progress = createProgress(chipsContainer);

                uploadToS3(file, function (pct) {
                    progress.setProgress(pct);
                }).then(function (result) {
                    progress.remove();
                    uploadedFiles.push({ url: result.url, name: result.name });
                    hiddenField.value = JSON.stringify(uploadedFiles);
                    renderChips();
                }).catch(function (err) {
                    progress.remove();
                    alert('Erreur: ' + err.message);
                });
            });
        }

        dzLabel.addEventListener('click', function (e) {
            if (e.target.closest('.chip-remove') || e.target.closest('.chip')) return;
            var tmpInput = document.createElement('input');
            tmpInput.type = 'file';
            tmpInput.multiple = true;
            tmpInput.accept = '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.odt,.ods,.odp,.png,.jpg,.jpeg,.gif,.webp,.txt,.csv,.zip';
            tmpInput.addEventListener('change', function () { handleFiles(this.files); });
            tmpInput.click();
        });

        ['dragenter', 'dragover'].forEach(function (ev) {
            dzLabel.addEventListener(ev, function (e) { e.preventDefault(); e.stopPropagation(); dzLabel.classList.add('is-drag'); });
        });
        ['dragleave', 'drop'].forEach(function (ev) {
            dzLabel.addEventListener(ev, function (e) { e.preventDefault(); e.stopPropagation(); dzLabel.classList.remove('is-drag'); });
        });
        dzLabel.addEventListener('drop', function (e) {
            e.preventDefault();
            dzLabel.classList.remove('is-drag');
            handleFiles(e.dataTransfer && e.dataTransfer.files);
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.file-drop').forEach(initSingleUpload);

        var lfDz = document.querySelector('.lf-dropzone');
        if (lfDz) initMultiUpload(lfDz);

        document.querySelectorAll('form').forEach(function (form) {
            form.addEventListener('submit', function (e) {
                if (form.querySelectorAll('.file-drop.is-uploading').length > 0) {
                    e.preventDefault();
                    alert('Veuillez attendre la fin de l\'upload avant de soumettre.');
                }
            });
        });
    });
})();