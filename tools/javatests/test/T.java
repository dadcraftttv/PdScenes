package app.pdscenes;
import android.content.Context; import java.io.File; import java.util.*; import org.puredata.core.PdBase;
public class T {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  public static void main(String[] a) throws Exception {
    File tmp=java.nio.file.Files.createTempDirectory("pd").toFile(); Context ctx=new Context(tmp);
    // curves round-trip
    for(Param p:Params.ALL){ if(p.toggle||p.choices!=null) continue; for(float t=0;t<=1.0001f;t+=0.25f){ float v=p.toValue(t); check(Math.abs(p.toNorm(v)-Math.min(t,1f))<1e-4,p.id+" curve t="+t+" v="+v);} }
    // randomize stays in safe range, skips locked and gain
    ParamStore.setLocked("feedback",true); float fb0=ParamStore.get("feedback"), g0=ParamStore.get("gain");
    boolean inRange=true; for(int i=0;i<2000;i++){ ParamStore.randomize(); for(Param p:Params.ALL){ if(!p.randomizable) continue; float v=ParamStore.get(p.id); if(p.id.equals("feedback")) continue; if(v<p.randMin-1e-3||v>p.randMax+1e-3) inRange=false; } }
    check(inRange,"randomize stays within safe ranges (2000 runs)");
    // dice morph: while the audio runs, Randomize glides there over MORPH_S; a slider moved meanwhile stays put
    AudioService.running=true; ParamStore.set("wet",0.1f); ParamStore.set("ring_freq",100f); ParamStore.setLocked("ring_freq",false);
    ParamStore.randomize(); float wetTo=-1; check(ParamStore.isMorphing()&&ParamStore.get("wet")==0.1f,"randomize starts a glide, nothing jumps yet");
    for(int i=0;i<45;i++) ParamStore.morphTick(0.033);   // ~1.5 s
    float wetMid=ParamStore.get("wet"); ParamStore.set("ring_freq",321f);
    for(int i=0;i<300&&ParamStore.isMorphing();i++) ParamStore.morphTick(0.033);
    check(!ParamStore.isMorphing()&&ParamStore.get("ring_freq")==321f,"the glide ends, and a slider moved by hand stays where it was put ("+ParamStore.get("ring_freq")+")");
    float wetEnd=ParamStore.get("wet"); check(Math.abs(wetMid-0.1f)<Math.abs(wetEnd-0.1f)||wetEnd==0.1f,"wet moved part way first ("+wetMid+") then to "+wetEnd);
    ParamStore.randomize(); ParamStore.morphTick(0.5); ParamStore.undo(); check(!ParamStore.isMorphing()&&ParamStore.get("wet")==wetEnd,"undo stops the glide and goes back");
    AudioService.running=false;
    check(ParamStore.get("feedback")==fb0,"locked param untouched by randomize");
    check(ParamStore.get("gain")==g0,"gain untouched by randomize");
    // undo restores
    Map<String,Float> before=ParamStore.snapshot(); ParamStore.randomize(); ParamStore.undo();
    check(ParamStore.snapshot().equals(before),"undo restores previous values");
    // nudge small
    ParamStore.setLocked("feedback",false); Map<String,Float> b2=ParamStore.snapshot(); ParamStore.nudge(0.12f);
    boolean small=true; for(Param p:Params.ALL){ if(!p.randomizable) continue; float d=Math.abs(p.toNorm(ParamStore.get(p.id))-p.toNorm(b2.get(p.id))); if(d>0.1201f) { // allowed only if clamped from outside safe range
        small=false; System.out.println("   big move "+p.id+" "+d);} }
    check(small,"nudge moves <= amount (within safe range)");
    // presets: save/read/round trip
    Map<String,Float> cur=ParamStore.snapshot(); String used=PresetManager.save(ctx,"My Test!!",cur);
    check(used.equals("My Test"),"sanitize name -> '"+used+"'");
    Map<String,Float> back=PresetManager.readUser(ctx,"My Test");
    boolean eq=back!=null; if(eq) for(Param p:Params.ALL){ if(!p.inPreset){ eq&=!back.containsKey(p.id); continue;} eq&=Math.abs(back.get(p.id)-cur.get(p.id))<1e-4; }
    check(eq,"user preset round-trips; gain excluded");
    check(PresetManager.userNames(ctx).equals(Arrays.asList("My Test")),"userNames lists it");
    try{ PresetManager.save(ctx,"Default",cur); check(false,"builtin name rejected"); }catch(java.io.IOException e){ check(true,"builtin name rejected: "+e.getMessage()); }
    check(PresetManager.delete(ctx,"My Test") && PresetManager.userNames(ctx).isEmpty(),"delete works");
    // parse tolerance
    PresetManager.Preset pr=PresetManager.parse("{\"values\":{\"wet\":5,\"echo_time\":10,\"bogus\":1,\"gain\":9}}");
    check(pr.values.get("wet")==1f && pr.values.get("echo_time")==50f && !pr.values.containsKey("bogus") && !pr.values.containsKey("gain"),"parse clamps, ignores unknown + gain");
    boolean threw=false; try{ PresetManager.parse("{\"values\":{\"x\":1}}"); }catch(org.json.JSONException e){threw=true;} check(threw,"parse rejects file with no known params");
    threw=false; try{ PresetManager.parse("not json"); }catch(org.json.JSONException e){threw=true;} check(threw,"parse rejects garbage");
    // built-ins applicable; apply preset leaves gain
    float gain=ParamStore.get("gain"); ParamStore.applyPreset(PresetManager.builtIn("Robot"));
    check(ParamStore.get("ring_freq")==150f && ParamStore.get("gain")==gain,"Robot preset applied, gain unchanged");
    // persistence
    ParamStore.setLocked("wet",true); ParamStore.save(ctx);
    ParamStore.set("ring_freq",999f); ParamStore.setLocked("wet",false);
    java.lang.reflect.Field f=ParamStore.class.getDeclaredField("loaded"); f.setAccessible(true); f.setBoolean(null,false);
    ParamStore.loadOnce(ctx);
    check(ParamStore.get("ring_freq")==150f && ParamStore.isLocked("wet"),"state restores from saved prefs (values + locks)");
    // pd forwarding only when running
    PdBase.sent.clear(); ParamStore.set("wet",0.3f); check(PdBase.sent.isEmpty(),"no Pd send while stopped");
    AudioService.running=true; ParamStore.set("wet",0.4f); check(PdBase.sent.size()==1,"Pd send while running: "+PdBase.sent);
    PdBase.sent.clear(); ParamStore.sendAllToPd(); int pdCount=0; for(Param p:Params.ALL) if(p.sendToPd) pdCount++;
    check(PdBase.sent.size()==pdCount && pdCount>=10,"sendAllToPd sends every Pd param ("+pdCount+"), not app-only ones");
    PdBase.sent.clear(); ParamStore.set("nudge_amount",0.1f); check(PdBase.sent.isEmpty() && Math.abs(ParamStore.get("nudge_amount")-0.1f)<1e-6,"nudge_amount is app-only (never sent to Pd)");
    // toggles
    ParamStore.set("echo_on",0.7f); check(ParamStore.get("echo_on")==1f,"toggle rounds 0.7 -> 1");
    ParamStore.set("echo_on",0.2f); check(ParamStore.get("echo_on")==0f,"toggle rounds 0.2 -> 0");
    ParamStore.set("echo_on",1f);
    Param ec=Params.byId("echo_on"); check(ec.format(1f).equals("on")&&ec.format(0f).equals("off"),"toggle formats on/off");
    check(Params.byId("nudge_amount").format(0.04f).equals("0.040"),"nudge strength shows 3 decimals: "+Params.byId("nudge_amount").format(0.04f));
    // randomize never flips toggles or touches smooth/nudge/gain
    float sm0=ParamStore.get("smooth"), n0=ParamStore.get("nudge_amount"); boolean tog=true;
    for(int i=0;i<500;i++){ ParamStore.randomize(); ParamStore.nudge(0.04f); if(ParamStore.get("echo_on")!=1f||ParamStore.get("ring_on")!=1f) tog=false; }
    check(tog && ParamStore.get("smooth")==sm0 && ParamStore.get("nudge_amount")==n0,"randomize/nudge leave toggles, smooth, nudge strength alone");
    // presets carry toggles but not smooth/nudge/gain
    String js=PresetManager.toJson("x",ParamStore.snapshot());
    check(js.contains("echo_on")&&js.contains("dry")&&!js.contains("smooth")&&!js.contains("nudge_amount")&&!js.contains("gain"),"preset JSON includes toggles/dry, excludes gain/smooth/nudge_amount");
    check(js.contains("dry_mv")&&js.contains("main_movers")&&!js.contains("gate_thresh_mv")&&!js.contains("comp_ratio_mv"),"preset keeps the dry mover and section switch, not the gate/compressor movers");
    ParamStore.set("gain_mv",13f); ParamStore.set("gain_mvdepth",0.9f); ParamStore.set("behavior_movers",1f); ParamStore.applyPreset(new java.util.HashMap<>());
    check(ParamStore.get("gain_mv")==13f&&ParamStore.get("gain_mvdepth")==0.9f&&ParamStore.get("behavior_movers")==1f,"loading a preset leaves the gain mover and the smoothing movers switch alone");
    boolean secOk=true; java.util.Set<String> ids=new java.util.HashSet<>(); for(Params.Section sc:Params.SECTIONS) ids.add(sc.id);
    for(Param p:Params.ALL) if(!ids.contains(p.section)) { secOk=false; System.out.println("   unknown section "+p.section+" for "+p.id); }
    check(secOk,"every param belongs to a known section");
    boolean nonEmpty=true; for(Params.Section sc:Params.SECTIONS){ int n=0; for(Param p:Params.ALL) if(p.section.equals(sc.id)) n++; if(n==0) nonEmpty=false; }
    check(nonEmpty,"every section has at least one param");
    System.out.println(fails==0?"ALL PASSED":(fails+" FAILED")); System.exit(fails==0?0:1);
  }
}
