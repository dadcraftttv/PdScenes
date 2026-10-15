package app.pdscenes;
import java.util.*;
public class K {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  static String err(String text){ try{ StemPack.parse(text,"x"); return null; }catch(IllegalArgumentException e){ return e.getMessage(); } }
  public static void main(String[] a){
    String txt="title: Neon Drive\nbpm: 108\nkey: A minor\nbars: 8\n\n# a comment\ndrums.wav      role: drums\nbass.wav  role: bass\npad_A.wav role: pad\npad_B.wav role: pad\nlead.wav role: lead bars: 16\nmy stem.wav role: texture section: b\n";
    StemPack p=StemPack.parse(txt,"fallback");
    check("Neon Drive".equals(p.title) && p.bpm==108 && p.key==9 && p.scale==1 && p.bars==8 && p.stems.size()==6,"pack.txt: title, bpm, key (A minor = 9, minor), bars, six stems");
    check(p.stems.get(4).bars==16 && "A".equals(p.stems.get(2).section) && "B".equals(p.stems.get(3).section) && "B".equals(p.stems.get(5).section)
        && "my stem.wav".equals(p.stems.get(5).file),"per-stem bars, sections from _A/_B and section:, file names with spaces");
    check(p.sections.equals(Arrays.asList("A","B")) && Math.abs(p.loopSeconds(p.stems.get(0))-8*4*60/108.0)<1e-9,"sections A, B; an 8-bar loop at 108 BPM is 17.8 s");
    check(Arrays.equals(StemPack.key("F# major"),new int[]{6,0}) && Arrays.equals(StemPack.key("Bb dorian"),new int[]{10,4})
        && Arrays.equals(StemPack.key("C"),new int[]{0,0}) && Arrays.equals(StemPack.key("e minor pentatonic"),new int[]{4,3}) && Arrays.equals(StemPack.key("Dm"),new int[]{2,1}),
        "keys: F# major, Bb dorian, C, E minor pentatonic, Dm");
    check(err("title: x\npad.wav role: pad").contains("bpm") && err("bpm: 100").contains("no stems") && err("bpm: 100\npad.wav role:").contains("no role")
        && err("bpm: 100\nkey: H\npad.wav role: pad").contains("note") && err("bpm: 100\nbars: 3.5\npad.wav role: pad").contains("whole number")
        && err("bpm: 100\nkey: C sparkly\npad.wav role: pad").contains("Unknown scale"),"mistakes get plain-words reasons");
    StringBuilder nine=new StringBuilder("bpm: 100\n"); for(int i=0;i<9;i++) nine.append("s").append(i).append(".wav role: pad\n");
    check(err(nine.toString()).contains("at most 8"),"at most 8 stems");
    // the arrangement
    StemArrangement ar=new StemArrangement(p);
    StemArrangement.Situation s=new StemArrangement.Situation();
    float[] lv=ar.tick(0.03,s);
    check(lv[2]==1 && lv[3]==0 && lv[0]==0 && lv[1]==0 && lv[4]==0 && lv[5]==0,"standing in a quiet room: only the pad (section A) "+Arrays.toString(lv));
    s.walking=true; s.pace=0.3f; lv=ar.tick(1,s);
    check(lv[0]==1,"walking: the drums join at once the first time");
    s.walking=false; lv=ar.tick(1,s);
    check(lv[0]==1,"...and stay at least 8 s after a change (no flapping), even if the walk stops at once");
    s.walking=true; for(int i=0;i<8;i++) lv=ar.tick(1,s);
    check(lv[0]==1 && lv[1]==1 && lv[4]==0,"walking: drums and bass join; the lead waits for a brisk walk or a lively room "+Arrays.toString(lv));
    s.pace=0.8f; for(int i=0;i<9;i++) lv=ar.tick(1,s);
    check(lv[4]==1,"a brisk walk brings the lead");
    s.walking=false; s.pace=0; s.night=true; for(int i=0;i<9;i++) lv=ar.tick(1,s);
    check(lv[0]==0 && lv[1]==0 && lv[4]==0 && lv[5]==1,"stopping at night: drums, bass and lead leave, the texture comes (only in section B, it stands in for A) "+Arrays.toString(lv));
    double sec=4*p.loopSeconds(p.stems.get(4)); for(double t=0;t<sec;t+=1) lv=ar.tick(1,s);
    check(ar.section()==1 && lv[3]==1 && lv[2]==0 && lv[5]==1,"after 4 loops of the longest stem, section B: pad_B and the night texture "+Arrays.toString(lv));
    // the pack takes over tempo, key and beat on the way to Pd, never the stored values
    Param bl=Params.byId("beat_level"), mk=Params.byId("music_key"), tm=Params.byId("tempo_mode"), tb=Params.byId("tempo_bpm");
    ParamStore.set("beat_level",0.6f); ParamStore.set("music_key",0f);
    PackPlayer.start(p);
    check(Modulation.output(tm,0f)==2f && Modulation.output(tb,100f)==108f && Modulation.output(mk,0f)==9f && Modulation.output(bl,0.6f)==0.6f,
        "while a pack plays: tempo locked (mode 2) at its 108 BPM, its key, the beat as set");
    PackPlayer.setDrums(1);
    check(Math.abs(Modulation.output(bl,0.6f)-0.18f)<1e-5,"while its drums play the app's beat steps back to 30% ("+Modulation.output(bl,0.6f)+")");
    PackPlayer.stop();
    check(Modulation.output(mk,0f)==0f && Modulation.output(bl,0.6f)==0.6f && ParamStore.get("music_key")==0f,"stopped: everything as set again, nothing stored changed");
    check(StemPack.tooLong(new double[]{60,60,60,60},new int[]{2,2,2,2})==null
        && StemPack.tooLong(new double[]{60,60,60,120},new int[]{2,2,2,1})==null
        && StemPack.tooLong(new double[]{128,128,128},new int[]{2,2,2}).contains("6:24"),
        "a pack must fit in memory: 4 minutes of stereo (a mono loop counts half); more gets a plain-words reason");
    check(Params.byId("stems_level")!=null && Params.byId("stems_level").inPreset,"Stems level is in the Mix, saved with presets");
    if(fails==0) System.out.println("ALL PASSED");
  }
}
