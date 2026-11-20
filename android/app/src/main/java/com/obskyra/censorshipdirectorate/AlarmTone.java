package com.obskyra.censorshipdirectorate;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;

/** Camera-independent 1 kHz loop played through regular phone media volume. */
public final class AlarmTone implements AutoCloseable {
    private final Context context;
    private MediaPlayer player;
    private boolean playing;
    private String lastError = "";

    public AlarmTone(Context context) { this.context = context.getApplicationContext(); }
    public boolean isPlaying() {
        if (!playing || player == null) return false;
        try { return player.isPlaying(); } catch (IllegalStateException e) { return false; }
    }
    public String getLastError() { return lastError; }

    public boolean setPlaying(boolean active) {
        if (active == playing) return lastError.isEmpty();
        if (!active) { stop(); return true; }
        stop();
        lastError = "";
        try {
            MediaPlayer media = new MediaPlayer();
            media.setAudioAttributes(new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build());
            media.setDataSource(waveFile().getAbsolutePath());
            media.setLooping(true);
            media.setVolume(0.90f, 0.90f);
            media.setOnErrorListener((mp, what, extra) -> {
                lastError = "Playback error " + what + "/" + extra;
                playing = false;
                Log.e("CensorshipAlarm", lastError);
                return true;
            });
            media.prepare();
            media.start();
            player = media;
            playing = media.isPlaying();
            return playing;
        } catch (IOException | RuntimeException e) {
            lastError = e.getClass().getSimpleName() + ": " + e.getMessage();
            Log.e("CensorshipAlarm", "Alarm sound failed", e);
            stop();
            return false;
        }
    }

    private File waveFile() throws IOException {
        File file = new File(context.getCacheDir(), "censorship-1000hz.wav");
        if (file.length() == 32044) return file;
        final int rate = 16000, size = rate * 2;
        try (FileOutputStream out = new FileOutputStream(file)) {
            out.write(new byte[]{'R','I','F','F'});
            le(out, 36 + size, 4);
            out.write(new byte[]{'W','A','V','E','f','m','t',' '});
            le(out, 16, 4); le(out, 1, 2); le(out, 1, 2);
            le(out, rate, 4); le(out, rate*2, 4);
            le(out, 2, 2); le(out, 16, 2);
            out.write(new byte[]{'d','a','t','a'});
            le(out, size, 4);
            for (int i=0;i<rate;i++) {
                int s = (int)(Math.sin(i*2*Math.PI*1000/rate)*32767*0.40);
                le(out, s, 2);
            }
        }
        return file;
    }

    private static void le(FileOutputStream out, int value, int bytes) throws IOException {
        for (int i=0;i<bytes;i++) out.write((value >>> (i*8)) & 255);
    }

    private void stop() {
        playing = false;
        MediaPlayer old = player;
        player = null;
        if (old != null) {
            try { if (old.isPlaying()) old.stop(); } catch (IllegalStateException ignored) {}
            old.release();
        }
    }
    @Override public void close() { stop(); }
}
