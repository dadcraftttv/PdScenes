package app.pdscenes;
import android.view.MotionEvent; import java.io.File; import java.util.*;
public class P2 {
    static int fails=0;
    static void check(boolean c,String m){System.out.println((c?"ok:   ":"FAIL: ")+m); if(!c)fails++;}
    static List<String> log=new ArrayList<>();
    static MotionEvent ev(int a,int idx,int[] ids,float[] xs,float[] ys){return new MotionEvent(a,idx,ids,xs,ys);}
    public static void main(String[] a){
        float[] g=SensorInput.toScene(0,0,9.80665f);
        check(Math.abs(g[2]+1f)<1e-6&&g[0]==0f||g[0]==-0f, "phone face-up (z=+9.8 m/s2) reads z=-1 g like iOS: "+Arrays.toString(g));
        float[] s=SensorInput.toScene(-19.6133f,4.903325f,0);
        check(Math.abs(s[0]-2f)<1e-4&&Math.abs(s[1]+0.5f)<1e-4,"x/y flip sign and scale to g: "+Arrays.toString(s));
        check(ScenePad.sampleSize(500)==1&&ScenePad.sampleSize(2048)==2&&ScenePad.sampleSize(4096)==4&&ScenePad.sampleSize(1023)==1,"image shrink factors");
        check(ScenePad.toGrid(0,0,400)==0&&ScenePad.toGrid(400,0,400)==320&&ScenePad.toGrid(200,0,400)==160&&ScenePad.toGrid(-5,0,400)==0&&ScenePad.toGrid(999,0,400)==320&&ScenePad.toGrid(150,100,200)==80,"grid mapping and clamping");

        ScenePad p=new ScenePad(new android.content.Context(new File(".")));
        p.setListener((t,f,x,y)->log.add(t+" "+f+" "+x+" "+y));
        p.w=400;p.h=280;
        p.onMeasure(400,0); check(p.mw==400&&p.mh==280,"no image: 10:7 pad "+p.mw+"x"+p.mh);
        // single finger: down, move, up
        p.onTouchEvent(ev(MotionEvent.ACTION_DOWN,0,new int[]{7},new float[]{200},new float[]{100}));
        p.onTouchEvent(ev(MotionEvent.ACTION_MOVE,0,new int[]{7},new float[]{400},new float[]{0}));
        p.onTouchEvent(ev(MotionEvent.ACTION_UP,0,new int[]{7},new float[]{400},new float[]{0}));
        check(log.equals(Arrays.asList("down 1 160 114","xy 1 320 0","up 1 320 0")),"one finger: "+log);
        // two fingers: numbering and reuse of the lowest free number
        log.clear();
        p.onTouchEvent(ev(MotionEvent.ACTION_DOWN,0,new int[]{3},new float[]{40},new float[]{40}));
        p.onTouchEvent(ev(MotionEvent.ACTION_POINTER_DOWN,1,new int[]{3,9},new float[]{40,360},new float[]{40,260}));
        p.onTouchEvent(ev(MotionEvent.ACTION_MOVE,0,new int[]{3,9},new float[]{44,356},new float[]{44,256}));
        p.onTouchEvent(ev(MotionEvent.ACTION_POINTER_UP,0,new int[]{3,9},new float[]{44,356},new float[]{44,256}));
        p.onTouchEvent(ev(MotionEvent.ACTION_POINTER_DOWN,1,new int[]{9,12},new float[]{356,100},new float[]{256,100}));
        check(log.get(0).startsWith("down 1 ")&&log.get(1).startsWith("down 2 ")&&log.get(2).startsWith("xy 1 ")&&log.get(3).startsWith("xy 2 ")&&log.get(4).startsWith("up 1 ")&&log.get(5).startsWith("down 1 "),"two fingers numbered 1,2; freed number 1 is reused: "+log);
        log.clear();
        p.onTouchEvent(ev(MotionEvent.ACTION_CANCEL,0,new int[]{9,12},new float[]{1,1},new float[]{1,1}));
        check(log.size()==2&&log.get(0).startsWith("up ")&&log.get(1).startsWith("up "),"cancel lifts every finger: "+log);
        log.clear();
        p.onTouchEvent(ev(MotionEvent.ACTION_MOVE,0,new int[]{9},new float[]{5},new float[]{5}));
        check(log.isEmpty(),"movement of an unknown finger is ignored");
        // wide image 320x160 => pad is half as tall; touches map across the picture
        p.setScene(null);
        java.io.File dir=new java.io.File("/tmp/padtest"); dir.mkdirs();
        try{ new java.io.FileOutputStream(new java.io.File(dir,"image.jpg")).close(); }catch(Exception e){}
        p.setScene(new SceneLibrary.Scene("x",dir,"x","","")); p.onMeasure(400,0);
        check(p.mh==200,"wide image keeps its shape: pad height "+p.mh);
        p.h=200; log.clear();
        p.onTouchEvent(ev(MotionEvent.ACTION_DOWN,0,new int[]{1},new float[]{400-1},new float[]{199}));
        check(log.size()==1&&log.get(0).startsWith("down 1 319 3"),"touch near bottom-right maps to ~(319,319): "+log);
        System.out.println(fails==0?"ALL PASSED":fails+" FAILED"); System.exit(fails==0?0:1);
    }
}
