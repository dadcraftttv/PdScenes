package app.pdscenes;
import java.util.*;
public class G {
  static int fails=0;
  static void check(boolean c,String m){ if(!c){fails++;System.out.println("FAIL: "+m);} else System.out.println("ok:   "+m); }
  public static void main(String[] a){
    SceneGraphics g=new SceneGraphics();
    g.apply(new Object[]{1005f,"image","smiley.png"});
    g.apply(new Object[]{1006f,"text","hello",3f,"there"});
    List<SceneGraphics.Item> s=g.snapshot();
    check(s.size()==2 && s.get(0).image && "smiley.png".equals(s.get(0).file) && !s.get(0).visible && s.get(0).x==160,
        "an image arrives hidden, in the middle");
    check(!s.get(1).image && "hello 3 there".equals(s.get(1).text) && s.get(1).visible,"a text arrives shown, numbers written Pd's way ("+s.get(1).text+")");
    int v=g.version();
    g.apply(new Object[]{1005f,"move",100f,200f}); g.apply(new Object[]{1005f,"visible",1f});
    g.apply(new Object[]{1005f,"rotate",45f}); g.apply(new Object[]{1005f,"alpha",0.5f}); g.apply(new Object[]{1005f,"scale",2f});
    SceneGraphics.Item im=g.snapshot().get(0);
    check(im.x==100 && im.y==200 && im.visible && im.rotate==45 && im.alpha==0.5f && im.scaleX==2 && im.scaleY==2 && g.version()>v,
        "move, visible, rotate, alpha and scale (one number = both ways) change it");
    g.apply(new Object[]{1006f,"text",42f}); g.apply(new Object[]{1006f,"size",22f});
    SceneGraphics.Item tx=g.snapshot().get(1);
    check("42".equals(tx.text) && tx.size==22,"text and size change the text");
    g.apply(new Object[]{1006f,"move",500f,500f});
    check(!g.snapshot().get(1).showing() && g.snapshot().get(0).showing(),"moved to 500 500 counts as hidden (the scenes' trick)");
    v=g.version();
    g.apply(new Object[]{2000f,"move",1f,1f}); g.apply(new Object[]{1005f,"wobble",1f}); g.apply(new Object[]{"x","move"});
    check(g.version()==v && g.snapshot().size()==2,"unknown ids and commands are ignored");
    g.apply(new Object[]{1007f,"text"});
    check(g.snapshot().size()==3 && "".equals(g.snapshot().get(2).text),"an empty text is fine");
    g.clear();
    check(g.snapshot().isEmpty(),"a scene stopping clears the screen");
    if(fails==0) System.out.println("ALL PASSED");
  }
}
