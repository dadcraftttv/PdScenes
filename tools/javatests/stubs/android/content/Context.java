package android.content;
import java.io.File; import java.util.*;
public class Context { public static final int MODE_PRIVATE=0; public File dir;
  public Context(File d){dir=d;} public <T> T getSystemService(Class<T> c){return null;} public File getFilesDir(){return dir;}
  public Context getApplicationContext(){return this;}
  public android.content.res.AssetManager getAssets(){return new android.content.res.AssetManager();}
  static final Map<String,Set<String>> sets=new HashMap<>();
  static final Map<String,String> store=new HashMap<>();
  public SharedPreferences getSharedPreferences(String n,int m){ return new SharedPreferences(){
    public String getString(String k,String d){ return store.getOrDefault(n+k,d);}
    public boolean getBoolean(String k,boolean d){ String v=store.get(n+k); return v==null?d:Boolean.parseBoolean(v);}
    public Set<String> getStringSet(String k,Set<String> d){ Set<String> v=sets.get(n+k); return v==null?d:new HashSet<>(v);}
    public Editor edit(){ return new Editor(){ java.util.List<String[]> w=new ArrayList<>();
      public Editor putString(String a,String b){w.add(new String[]{a,b});return this;}
      public Editor putBoolean(String a,boolean b){w.add(new String[]{a,String.valueOf(b)});return this;}
      Map<String,Set<String>> ws=new HashMap<>();
      public Editor putStringSet(String a,Set<String> b){ws.put(a,new HashSet<>(b));return this;}
      public Editor clear(){ w.clear(); ws.clear(); store.keySet().removeIf(k->k.startsWith(n)); sets.keySet().removeIf(k->k.startsWith(n)); return this; }
      public void apply(){for(String[] kv:w)store.put(n+kv[0],kv[1]); for(Map.Entry<String,Set<String>> e:ws.entrySet())sets.put(n+e.getKey(),e.getValue());} }; } }; } }
