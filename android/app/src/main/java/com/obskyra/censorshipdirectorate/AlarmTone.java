package com.obskyra.censorshipdirectorate;

import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;
import android.util.Log;

/**
 * Streams a 1 kHz tone on the Android alarm audio channel.
 *
 * Unlike a static AudioTrack this doesn't depend on device-specific loop-point
 * support. Audio output is independent from camera and face detection.
 */
public final class AlarmTone implements AutoCloseable {
    private static final String TAG = "CensorshipAlarm";
    private AudioTrack player;
    private Thread writer;
    private volatile boolean running;
    private boolean playing;

    public synchronized boolean isPlaying() { return playing; }

    public synchronized boolean setPlaying(boolean active) {
        if (active == playing) return true;
        if (!active) { stop(); return true; }
        stop();
        final int sampleRate = 16000;
        try {
            int minimum = AudioTrack.getMinBufferSize(sampleRate,
                AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT);
            if (minimum <= 0) throw new IllegalStateException("No audio output buffer");
            final AudioTrack track = new AudioTrack.Builder()
                .setAudioAttributes(new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build())
                .setAudioFormat(new AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(sampleRate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build())
                .setTransferMode(AudioTrack.MODE_STREAM)
                .setBufferSizeInBytes(Math.max(minimum, sampleRate / 5 * 2))
                .build();
            if (track.getState() != AudioTrack.STATE_INITIALIZED) {
                track.release();
                throw new IllegalStateException("AudioTrack did not initialize");
            }
            track.setVolume(0.65f);
            track.play();
            player = track;
            running = true;
            playing = true;
            writer = new Thread(() -> {
                short[] samples = new short[sampleRate / 10];
                for (int i = 0; i < samples.length; i++)
                    samples[i] = (short) (Math.sin(i * 2.0 * Math.PI * 1000 / sampleRate)
                                          * 32767 * 0.27);
                while (running) {
                    try {
                        int written = track.write(samples, 0, samples.length,
                                                  AudioTrack.WRITE_BLOCKING);
                        if (written < 0) {
                            Log.e(TAG, "AudioTrack write failed: " + written);
                            break;
                        }
                    } catch (RuntimeException error) {
                        Log.e(TAG, "Audio output stopped", error);
                        break;
                    }
                }
            }, "CensorshipAlarmTone");
            writer.setDaemon(true);
            writer.start();
            return true;
        } catch (RuntimeException error) {
            Log.e(TAG, "Cannot play alarm tone", error);
            stop();
            return false;
        }
    }

    private void stop() {
        running = false;
        playing = false;
        AudioTrack track = player;
        player = null;
        writer = null;
        if (track != null) {
            try {
                if (track.getPlayState() == AudioTrack.PLAYSTATE_PLAYING)
                    track.pause();
                track.flush();
            } catch (IllegalStateException error) {
                Log.w(TAG, "Stopping audio failed", error);
            }
            track.release();
        }
    }

    @Override public synchronized void close() { stop(); }
}
