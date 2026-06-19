// Apps Script web app：以「你」的身份讀寫你 Drive 的 library 資料夾。
// 部署：Deploy > New deployment > Web app；Execute as Me；Who has access Anyone。
// 把 LIBRARY_FOLDER_ID 換成 Drive 上 library 資料夾（含 manifest.json / progress.json / audio/）的 ID。
var LIBRARY_FOLDER_ID = "PASTE_DRIVE_LIBRARY_FOLDER_ID";

function _folder() { return DriveApp.getFolderById(LIBRARY_FOLDER_ID); }

function _fileByName(folder, name) {
  var it = folder.getFilesByName(name);
  return it.hasNext() ? it.next() : null;
}

function _readJson(folder, name, fallback) {
  var f = _fileByName(folder, name);
  if (!f) return fallback;
  return JSON.parse(f.getBlob().getDataAsString());
}

function _writeJson(folder, name, obj) {
  var f = _fileByName(folder, name);
  var content = JSON.stringify(obj);
  if (f) f.setContent(content);
  else folder.createFile(name, content, "application/json");
}

function _audioFolder(folder) {
  var it = folder.getFoldersByName("audio");
  return it.hasNext() ? it.next() : null;
}

function _audioUrl(audioFolder, audioFile) {
  if (!audioFolder || !audioFile) return null;
  var it = audioFolder.getFilesByName(audioFile);
  if (!it.hasNext()) return null;
  var f = it.next();
  f.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  return "https://drive.google.com/uc?export=download&id=" + f.getId();
}

function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  var action = (e && e.parameter && e.parameter.action) || "manifest";
  var folder = _folder();
  if (action === "progress") {
    return _json(_readJson(folder, "progress.json",
      { version: 1, done_clips: [], attempts: [] }));
  }
  var manifest = _readJson(folder, "manifest.json",
    { version: 1, updated_at: null, shows: [] });
  var audio = _audioFolder(folder);
  (manifest.shows || []).forEach(function (show) {
    (show.clips || []).forEach(function (clip) {
      clip.audio_url = _audioUrl(audio, clip.audio_file);
    });
  });
  return _json(manifest);
}

function doPost(e) {
  try {
    var folder = _folder();
    var body = JSON.parse(e.postData.contents);   // {clip_id, attempt?}
    var progress = _readJson(folder, "progress.json",
      { version: 1, done_clips: [], attempts: [] });
    if (body.clip_id && progress.done_clips.indexOf(body.clip_id) === -1) {
      progress.done_clips.push(body.clip_id);
    }
    if (body.attempt) progress.attempts.push(body.attempt);
    _writeJson(folder, "progress.json", progress);
    return _json({ ok: true, done_clips: progress.done_clips.length });
  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}
