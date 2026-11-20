package com.obskyra.censorshipdirectorate;

import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.util.Log;

/** Mic activity meter only: no recording, uploading or speech transcription. */
public final class AudioMonitor implements AutoCloseable {
    public interface Callback { void onLevel(float level); }
    private final Callback callback;
    private Thread thread;
    private volatile boolean running;

    public AudioMonitor(Callback callback) { this.callback = callback; }

    @SuppressWarnings("MissingPermission")
    public void start() {
        if (running) return;
        running=true;
        thread=new Thread(this::loop,"CensorshipMic");
        thread.start();
    }

    @SuppressWarnings("MissingPermission")
    private void loop() {
        final int rate=16000;
        int size=Math.max(rate/5,AudioRecord.getMinBufferSize(rate,
            AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT));
        AudioRecord record=null;
        try {
            record=new AudioRecord(MediaRecorder.AudioSource.MIC,rate,
                AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,size*2);
            if (record.getState()!=AudioRecord.STATE_INITIALIZED) return;
            record.startRecording();
            short[] buffer=new short[rate/20];
            int ticks=0;
            while(running) {
                int n=record.read(buffer,0,buffer.length);
                if(n<=0) continue;
                double squares=0;
                for(int i=0;i<n;i++) {
                    double v=buffer[i]/32768.0;
                    squares+=v*v;
                }
                float rms=(float)Math.sqrt(squares/n);
                if (++ticks%2==0) callback.onLevel(rms);
            }
        } catch (RuntimeException error) {
            Log.w("CensorshipMic","Microphone unavailable",error);
        } finally {
            if (record!=null) {
                try { record.stop(); } catch (IllegalStateException ignored) {}
                record.release();
            }
        }
    }

    @Override public void close() {
        running=false;
        if(thread!=null) {
            thread.interrupt();
            try { thread.join(500); } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }
    }
}
