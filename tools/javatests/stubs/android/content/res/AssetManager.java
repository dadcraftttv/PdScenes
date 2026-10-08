package android.content.res;
import java.io.*;
/** No assets in the plain-Java tests: every folder lists as empty. */
public class AssetManager { public String[] list(String path) throws IOException { return new String[0]; }
  public InputStream open(String path) throws IOException { throw new FileNotFoundException(path); } }
