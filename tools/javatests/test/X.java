package app.pdscenes;
import java.util.*;
public class X {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  // rotation vector (x,y,z,w) for a rotation of angle a about axis (ax,ay,az)
  static float[] rv(double a,double ax,double ay,double az){ double n=Math.sqrt(ax*ax+ay*ay+az*az); double s=Math.sin(a/2)/n; return new float[]{(float)(ax*s),(float)(ay*s),(float)(az*s),(float)Math.cos(a/2)}; }
  static boolean near(float a,float b,float tol){ float d=Math.abs(a-b)%360f; return Math.min(d,360f-d)<=tol; }
  public static void main(String[] a){
    // ---- heading: device axes -> world (East,North,Up). Rotation about Up (z) by -h turns the top edge from North to heading h.
    check(near(PhoneContext.headingDegrees(rv(0,0,0,1)),0f,0.5f),"flat, top edge north -> 0");
    check(near(PhoneContext.headingDegrees(rv(-Math.PI/2,0,0,1)),90f,0.5f),"flat, top edge east -> 90");
    check(near(PhoneContext.headingDegrees(rv(Math.PI,0,0,1)),180f,0.5f),"flat, top edge south -> 180");
    check(near(PhoneContext.headingDegrees(rv(Math.PI/2,0,0,1)),270f,0.5f),"flat, top edge west -> 270");
    // upright, facing north: stand the phone up (rotate about East by +90 deg so the top edge points Up; the back then faces North)
    check(near(PhoneContext.headingDegrees(rv(Math.PI/2,1,0,0)),0f,0.5f),"upright, back facing north -> 0");
    // upright facing east: first stand up, then turn the whole thing -90 about Up: q = qz(-90) * qx(90)
    float[] qx=rv(Math.PI/2,1,0,0), qz=rv(-Math.PI/2,0,0,1);
    float[] q=mul(qz,qx);
    check(near(PhoneContext.headingDegrees(q),90f,0.5f),"upright, back facing east -> 90");
    // continuity while tilting up from flat (top edge north) to upright: heading stays 0
    boolean steady=true; for(int d=0;d<=90;d+=5){ if(!near(PhoneContext.headingDegrees(rv(Math.toRadians(d),1,0,0)),0f,1f)) steady=false; }
    check(steady,"tilting from flat to upright keeps heading steady");
    check(PhoneContext.headingDegrees(new float[]{0,0,0})>=0,"3-value vector (no w) works");
    check(PhoneContext.headingDegrees(null)<0&&PhoneContext.headingDegrees(new float[]{1})<0,"unusable vector -> -1");
    // ---- brightness ----
    PhoneContext.reset(); check(PhoneContext.brightness()==0.5f,"no light sensor yet: middle (no change)");
    PhoneContext.onLight(300f,0); float bSteady=PhoneContext.brightness(0);
    check(bSteady>0.4f&&bSteady<0.6f,"steady room reads about the middle: "+bSteady);
    PhoneContext.onLight(330f,1); check(Math.abs(PhoneContext.brightness(1)-bSteady)<0.1f,"small flicker barely moves it: "+PhoneContext.brightness(1));
    // the real readings from the phone: lamp ~3000 lux, a finger over the sensor under the lamp ~15 lux
    PhoneContext.reset(); PhoneContext.onLight(3000f,0); PhoneContext.onLight(15f,1); float covered=PhoneContext.brightness(1.5);
    PhoneContext.onLight(3000f,2); float uncovered=PhoneContext.brightness(2.5);
    check(covered<0.15f&&uncovered>0.85f,"finger over the sensor under a lamp spans the range: "+covered+" -> "+uncovered);
    PhoneContext.onLight(15f,3); float settled=PhoneContext.brightness(3+600);
    check(settled>0.3f&&settled<0.6f,"staying dark settles back toward the middle: "+settled);
    PhoneContext.reset(); PhoneContext.onLight(1f,0); float night=PhoneContext.brightness(600);
    PhoneContext.reset(); PhoneContext.onLight(50000f,0); float sun=PhoneContext.brightness(600);
    check(sun>night+0.15f,"a sunny street still reads above a dark room once settled: "+night+" "+sun);
    // ---- pocket ----
    PhoneContext.reset(); PhoneContext.onLight(2f);
    check(!PhoneContext.inPocket(100),"no proximity reading: not pocket");
    PhoneContext.onProximity(true,100.0);
    check(!PhoneContext.inPocket(100.5),"near for half a second: not yet");
    check(PhoneContext.inPocket(101.2),"near for over a second and dark: pocket");
    PhoneContext.onLight(300f);
    check(!PhoneContext.inPocket(105),"near but bright (hand over the phone in daylight): not pocket");
    PhoneContext.onLight(2f); PhoneContext.onProximity(false,106); check(!PhoneContext.inPocket(110),"taken out: not pocket");
    PhoneContext.reset(); PhoneContext.onProximity(true,0); check(PhoneContext.inPocket(2),"no light sensor: proximity alone is enough");
    // ---- climb ----
    PhoneContext.reset(); double t=0; for(;t<60;t+=0.2) PhoneContext.onPressure(1013f,t);
    check(Math.abs(PhoneContext.climb())<0.01f,"steady air: no climb");
    float p=1013f; for(int i=0;i<150;i++){ t+=0.2; p-=0.0054f; PhoneContext.onPressure(p,t); }   // 0.027 hPa/s = about 0.22 m/s up for 30 s
    float up=PhoneContext.climb(); check(up>0.4f&&up<=1f,"climbing stairs: positive "+up);
    for(int i=0;i<600;i++){ t+=0.2; PhoneContext.onPressure(p,t); }
    check(Math.abs(PhoneContext.climb())<0.05f,"stopping on a landing settles back: "+PhoneContext.climb());
    for(int i=0;i<150;i++){ t+=0.2; p+=0.0054f; PhoneContext.onPressure(p,t); }
    check(PhoneContext.climb()<-0.4f,"going down: negative "+PhoneContext.climb());
    PhoneContext.reset(); for(int i=0;i<300;i++){ t+=0.2; PhoneContext.onPressure(1013f+(i%2==0?0.03f:-0.03f),t); }
    check(Math.abs(PhoneContext.climb())<0.15f,"sensor noise alone stays small: "+PhoneContext.climb());
    PhoneContext.onPressure(900f,t+100); check(PhoneContext.climb()==0f,"a long gap restarts the averages");
    // ---- selector with pocket ----
    WorldSelector s=new WorldSelector(); Set<String> all=new HashSet<>(Arrays.asList(WorldSelector.PRIORITY));
    check(Arrays.asList(WorldSelector.PRIORITY).indexOf("pocket")==WorldSelector.PRIORITY.length-1,"pocket is the fallback: every other world outranks it");
    String w=null;
    // rustle: loud bursts with ordinary gaps between them (not walking)
    for(int i=0;i<400;i++) w=s.update(0.1,(i%10<3)?-10f:-42f,false,true,12*60,all);
    check("pocket".equals(w),"rustle bursts in a pocket -> pocket, not flux: "+w);
    s.reset(); for(int i=0;i<400;i++) w=s.update(0.1,(i%10<3)?-10f:-60f,false,true,12*60,all);
    check("tranquil".equals(w),"rustle in a pocket in a quiet room -> tranquil: "+w);
    s.reset(); for(int i=0;i<400;i++) w=s.update(0.1,-30f+((i%10<3)?8f:0f),false,true,12*60,all);
    check("flux".equals(w),"a loud shop heard from a pocket -> flux: "+w);
    s.reset(); for(int i=0;i<400;i++) w=s.update(0.1,-30f,false,false,12*60,all);
    check(w==null,"the same shop out of the pocket is not loud enough for flux (the pocket muffles): "+w);
    s.reset(); for(int i=0;i<400;i++) w=s.update(0.1,-10f,true,true,12*60,all);
    check("kinetic".equals(w),"walking with the phone in a pocket -> kinetic: "+w);
    s.reset(); for(int i=0;i<400;i++) w=s.update(0.1,-10f,false,true,2*60,all);
    check("ghost".equals(w),"late at night in a pocket -> ghost: "+w);
    for(int i=0;i<400;i++) w=s.update(0.1,-40f,false,false,12*60,all);
    check(w==null,"phone out of the pocket in the day, ordinary room: back to nothing: "+w);
    // ---- movers use the new sensors ----
    Modulation.reset(); ParamStore.set("wet",0.4f);
    M.setMover("wet",13,2f,1f);
    PhoneContext.reset(); PhoneContext.onLight(0.5f); M.sent.clear(); M.run(2,0.033); float dark=M.min(M.sent.get("wet"));
    PhoneContext.onLight(20000f); M.sent.clear(); M.run(2,0.033); float sunny=M.max(M.sent.get("wet"));
    check(sunny>dark+0.2f,"Brighter = higher: dark "+dark+", sunny "+sunny);
    Modulation.reset(); M.setMover("wet",14,2f,1f); PhoneContext.reset(); PhoneContext.onLight(1f); PhoneContext.onProximity(false); M.sent.clear(); M.run(2,0.033); float out=M.min(M.sent.get("wet"));
    PhoneContext.onProximity(true,PhoneContext.now()-5); M.sent.clear(); M.run(2,0.033); float in=M.max(M.sent.get("wet"));
    check(in>out+0.2f,"In pocket = higher: out "+out+", in "+in);
    Modulation.reset(); M.setMover("wet",15,2f,1f); PhoneContext.reset(); double t2=0; for(;t2<40;t2+=0.2) PhoneContext.onPressure(1000f,t2);
    float pp=1000f; for(int i=0;i<100;i++){ t2+=0.2; pp-=0.006f; PhoneContext.onPressure(pp,t2);} M.sent.clear(); M.run(2,0.033);
    check(M.max(M.sent.get("wet"))>0.4f+0.1f,"Climbing = higher: "+M.max(M.sent.get("wet")));
    System.out.println(fails==0?"ALL PASSED":fails+" FAILED");
  }
  static float[] mul(float[] a,float[] b){ // quaternion a*b, (x,y,z,w)
    return new float[]{ a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1], a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0], a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3], a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2] }; }
}
