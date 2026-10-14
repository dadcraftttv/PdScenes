package app.pdscenes;
public class B {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  static double t=0;
  static boolean started, ended;
  static void run(double secs, boolean calm){ for(double end=t+secs;t<end;t+=0.033){ if(CalmBuild.tick(0.033,calm)){ if(CalmBuild.phase()==CalmBuild.Phase.RISING) started=true; else ended=true; } } }
  static float out(String id){ return Modulation.output(Params.byId(id),ParamStore.get(id)); }
  public static void main(String[] a){
    Param cb=Params.byId("calm_build");
    check(cb!=null && cb.def==0f && !cb.inPreset && !cb.sendToPd,"Calm builds: off by default, the user's own (not in presets), app-only");
    CalmBuild.reset(); Modulation.reset();
    ParamStore.set("music_pad",0.3f); ParamStore.set("reverb_mix",0f); ParamStore.set("music_harm",0.5f); ParamStore.set("music_res",0.5f);
    run(29,true);
    check(CalmBuild.level()==0 && CalmBuild.phase()==CalmBuild.Phase.WAITING && !started,"nothing in the first 30 s of calm");
    run(2,true);
    check(started && CalmBuild.phase()==CalmBuild.Phase.RISING,"then a build starts");
    run(38,true);
    check(out("music_pad")>0.3f && Math.abs(out("music_res")-0.5f)<1e-6 && Math.abs(out("music_harm")-0.5f)<1e-6,
        "a quarter of the way up only the pad has grown (pad "+out("music_pad")+", room notes "+out("music_res")+")");
    run(146,true);
    check(CalmBuild.phase()==CalmBuild.Phase.HOLDING && CalmBuild.level()==1f,"after ~3 min it holds at the top");
    check(Math.abs(out("music_pad")-0.42f)<1e-3 && Math.abs(out("music_harm")-0.7f)<1e-3 && out("reverb_mix")==0f,
        "at the top every layer is up 40% (pad "+out("music_pad")+", harmony "+out("music_harm")+"), and a part at 0 stays at 0 (reverb "+out("reverb_mix")+")");
    check(ParamStore.get("music_pad")==0.3f,"...the stored values never change");
    run(60+60,true); float mid=CalmBuild.level();
    check(CalmBuild.phase()==CalmBuild.Phase.FALLING && mid>0.4f && mid<0.6f,"then it eases back ("+mid+" halfway)");
    run(61,true);
    check(ended && CalmBuild.phase()==CalmBuild.Phase.RESTING && CalmBuild.level()==0,"and ends, resting");
    started=false; run(170,true);
    check(!started,"no new build while resting (3 min)");
    run(10+31,true);
    check(started,"after the rest and another 30 s of calm, the next one");
    run(60,true); float before=CalmBuild.level();
    run(5.1,false);
    check(before>0.3f && CalmBuild.level()==0f && CalmBuild.phase()==CalmBuild.Phase.WAITING,"walking or a lively room: gone within 5 s ("+before+" -> "+CalmBuild.level()+")");
    run(20,true);
    check(CalmBuild.level()==0f,"...and it waits for calm again");
    if(fails==0) System.out.println("ALL PASSED");
  }
}
