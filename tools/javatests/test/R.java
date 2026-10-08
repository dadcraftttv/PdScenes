package app.pdscenes;
public class R {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  public static void main(String[] a){
    ParamStore.set("gain",7f); ParamStore.set("echo_time",900f); ParamStore.set("music_on",1f);
    ParamStore.set("music_key",5f); ParamStore.set("music_scale",3f); ParamStore.set("reverb_mix_mv",3f);
    ParamStore.setLocked("echo_time",true);
    ParamStore.resetAll();
    boolean all=true; String bad="";
    for (Param p: Params.ALL) if (ParamStore.get(p.id)!=p.clamp(p.def)) { all=false; bad+=p.id+" "; }
    check(all,"every parameter is back at its default "+bad);
    check(!ParamStore.isLocked("echo_time"),"locks are cleared");
    check(ParamStore.get("music_on")==0f && ParamStore.get("music_key")==0f && ParamStore.get("music_scale")==0f,"music is off in C major");
    check(ParamStore.get("gain")==2.5f,"input gain is the new default 2.5");
    ParamStore.undo();
    check(ParamStore.get("echo_time")==900f,"undo brings the old settings back");
    System.out.println(fails==0?"ALL PASSED":fails+" FAILED");
  }
}
