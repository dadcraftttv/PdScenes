package app.pdscenes;
import java.util.*;
public class I {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  static float out(String id){ return Modulation.output(Params.byId(id),ParamStore.get(id)); }
  public static void main(String[] a){
    Modulation.reset();
    ParamStore.set("wet",0.5f); ParamStore.set("ring_mix",0f); ParamStore.set("gc_amount",0.4f); ParamStore.set("feedback",0.6f);
    ParamStore.set("music_pad",0.33f); ParamStore.set("gain",2.5f);
    Param in=Params.byId("intensity");
    check(in!=null && in.def==0.5f && !in.inPreset,"Intensity: default 0.5, not in presets");
    ParamStore.set("intensity",0.5f);
    check(out("wet")==0.5f && out("gc_amount")==0.4f && out("feedback")==0.6f,"at 0.5 everything plays as set");
    ParamStore.set("intensity",0f);
    check(Math.abs(out("wet")-0.2f)<1e-4 && out("gc_amount")==0f && Math.abs(out("feedback")-0.3f)<1e-4,
        "at 0: echo level 0.5 -> "+out("wet")+", glitch amount off "+out("gc_amount")+", feedback 0.6 -> "+out("feedback"));
    check(ParamStore.get("wet")==0.5f,"...the stored value stays 0.5");
    ParamStore.set("intensity",1f);
    Param wet=Params.byId("wet"), fb=Params.byId("feedback");
    check(Math.abs(out("wet")-wet.randMax)<1e-4 && Math.abs(out("gc_amount")-0.6f)<1e-4 && out("feedback")<=Math.max(0.6f,fb.randMax)+1e-4 && out("feedback")>0.6f,
        "at 1: echo level up to its safe top "+out("wet")+", glitch 0.4 -> "+out("gc_amount")+", feedback "+out("feedback"));
    check(out("ring_mix")==0f,"an effect at 0 never comes on ("+out("ring_mix")+")");
    check(out("music_pad")==0.33f && out("gain")==2.5f,"the pad and input gain are left alone");
    ParamStore.set("feedback",0.8f);
    check(out("feedback")<=0.8f+1e-4 && out("feedback")>=0.8f-1e-4,"a slider set above the safe range isn't pushed further, or pulled down ("+out("feedback")+")");
    // every scaled value stays inside its slider's range at both ends
    boolean inside=true;
    for(String id:Intensity.scaled()){ Param p=Params.byId(id); if(p==null){inside=false;System.out.println("unknown "+id);continue;}
      for(float t:new float[]{0f,1f}){ ParamStore.set("intensity",t); ParamStore.set(id,p.max); float v=out(id); ParamStore.set(id,p.def); float w=out(id);
        if(v<p.min-1e-4||v>p.max+1e-4||w<p.min-1e-4||w>p.max+1e-4){inside=false;System.out.println(id+" "+t+" "+v+" "+w);} } }
    check(inside,"every scaled parameter exists and stays within its range");
    if(fails==0) System.out.println("ALL PASSED");
  }
}
