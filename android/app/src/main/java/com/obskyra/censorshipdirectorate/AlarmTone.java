package com.obskyra.censorshipdirectorate;

import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;

public final class AlarmTone implements AutoCloseable {
    private AudioTrack player;
    private boolean playing;
    public boolean isPlaying() { return playing; }

    public void setPlaying(boolean active) {
        if (active == playing) return;
        if (!active) { close(); return; }
        final int rate=16000;
        short[] samples=new short[rate];
        for (int i=0;i<samples.length;i++) {
            samples[i]=(short)(Math.sin(i*2*Math.PI*1000/rate)*32767*0.20);
        }
        try {
            player=new AudioTrack(AudioManager.STREAM_MUSIC,rate,
                AudioFormat.CHANNEL_OUT_MONO,AudioFormat.ENCODING_PCM_16BIT,
                samples.length*2,AudioTrack.MODE_STATIC);
            if(player.getState()!=AudioTrack.STATE_INITIALIZED) {
                close();return;
            }
            player.write(samples,0,samples.length);
            player.setLoopPoints(0,samples.length,-1);
            player.setVolume(0.3f);
            player.play();
            playing=true;
        } catch(RuntimeException error) {
            close();
        }
    }

    @Override public void close() {
        playing=false;
        if(player!=null) {
            try { player.pause();player.flush(); } catch(IllegalStateException ignored) {}
            player.release();
            player=null;
        }
    }
}
