package android.content;
import java.util.Set;
public interface SharedPreferences { String getString(String k,String d); boolean getBoolean(String k,boolean d); Set<String> getStringSet(String k,Set<String> d); Editor edit();
  interface Editor { Editor putString(String k,String v); Editor putBoolean(String k,boolean v); Editor putStringSet(String k,Set<String> v); Editor clear(); void apply(); } }
