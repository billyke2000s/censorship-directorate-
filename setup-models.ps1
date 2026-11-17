$ErrorActionPreference = 'Stop'
$modelDirectory = Join-Path $PSScriptRoot 'models'
New-Item -ItemType Directory -Force -Path $modelDirectory | Out-Null
$base = 'https://storage.googleapis.com/mediapipe-models'
foreach ($name in @('face_landmarker', 'hand_landmarker')) {
    $destination = Join-Path $modelDirectory "$name.task"
    $temporary = "$destination.download"
    Invoke-WebRequest -Uri "$base/$name/$name/float16/1/$name.task" -OutFile $temporary
    Move-Item -LiteralPath $temporary -Destination $destination -Force
}
