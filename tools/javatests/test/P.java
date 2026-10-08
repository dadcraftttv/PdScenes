package app.pdscenes;
import java.util.*;
public class P { public static void main(String[] a){ for(String n: PresetManager.builtInNames()){ Map<String,Float> m=PresetManager.builtIn(n); boolean ok=true; for(Map.Entry<String,Float> e:m.entrySet()){ Param p=Params.byId(e.getKey()); if(p==null||!p.inPreset||e.getValue()<p.min-1e-6||e.getValue()>p.max+1e-6) ok=false; }
 System.out.println((ok?"ok:   ":"FAIL: ")+"built-in '"+n+"' valid ("+m.size()+" values)"); } } }
