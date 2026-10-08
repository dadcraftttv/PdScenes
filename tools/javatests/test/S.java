package app.pdscenes;
import java.io.*; import java.nio.file.*; import java.util.*; import java.util.zip.*;
public class S {
    static int fails = 0;
    static void check(boolean c, String m) { System.out.println((c ? "ok:   " : "FAIL: ") + m); if (!c) fails++; }
    static byte[] zip(String... nameContent) throws IOException {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        try (ZipOutputStream z = new ZipOutputStream(b)) {
            for (int i = 0; i < nameContent.length; i += 2) {
                z.putNextEntry(new ZipEntry(nameContent[i]));
                z.write(nameContent[i + 1].getBytes("UTF-8")); z.closeEntry();
            }
        }
        return b.toByteArray();
    }
    static final String PLIST = "<plist><dict><key>info</key><dict><key>name</key><string>Echo &amp; Co</string>"
            + "<key>author</key><string>Jane</string><key>description</key><string>Hi</string></dict></dict></plist>";
    public static void main(String[] a) throws Exception {
        File dir = Files.createTempDirectory("scenes").toFile();
        SceneLibrary.Scene s = SceneLibrary.importZip(new ByteArrayInputStream(zip(
                "Foo.rj/_main.pd", "#N canvas;", "Foo.rj/Info.plist", PLIST, "Foo.rj/rj/x.pd", "x",
                "__MACOSX/Foo.rj/._main.pd", "junk")), "ignored", dir);
        check(s.dirName.equals("Foo.rj") && s.name.equals("Echo & Co") && s.author.equals("Jane"), "folder zip: " + s.dirName + " / " + s.name + " / " + s.author);
        check(new File(dir, "Foo.rj/rj/x.pd").isFile() && !new File(dir, "__MACOSX").exists(), "nested files kept, Mac junk dropped");
        SceneLibrary.Scene f = SceneLibrary.importZip(new ByteArrayInputStream(zip("_main.pd", "#N canvas;", "a.wav", "w")), "My Scene.rj.zip", dir);
        check(f.dirName.equals("My Scene.rj") && f.name.equals("My Scene"), "flat zip named from the file: " + f.dirName);
        SceneLibrary.Scene w = SceneLibrary.importZip(new ByteArrayInputStream(zip("wrap/Deep.rj/_main.pd", "#N canvas;")), "x", dir);
        check(w.dirName.equals("Deep.rj"), "scene one folder down: " + w.dirName);
        SceneLibrary.importZip(new ByteArrayInputStream(zip("Foo.rj/_main.pd", "#N canvas;")), "x", dir);
        check(!new File(dir, "Foo.rj/rj").exists() && SceneLibrary.find(dir, "Foo.rj").name.equals("Foo"), "re-import replaces the old copy; no plist falls back to folder name");
        check(SceneLibrary.list(dir).size() == 3 && Arrays.stream(dir.list()).noneMatch(n -> n.startsWith(".import")), "list finds 3 scenes, no staging left over");
        try { SceneLibrary.importZip(new ByteArrayInputStream(zip("readme.txt", "hi")), "x", dir); check(false, "zip without _main.pd rejected"); }
        catch (IOException e) { check(e.getMessage().contains("_main.pd"), "zip without _main.pd rejected: " + e.getMessage()); }
        try { SceneLibrary.importZip(new ByteArrayInputStream(zip("../evil.txt", "x", "_main.pd", "y")), "x", dir); check(false, "zip-slip rejected"); }
        catch (IOException e) { check(!new File(dir.getParentFile(), "evil.txt").exists(), "zip-slip rejected: " + e.getMessage()); }
        try { SceneLibrary.importZip(new ByteArrayInputStream("not a zip".getBytes()), "x", dir); check(false, "garbage rejected"); }
        catch (IOException e) { check(true, "non-zip rejected: " + e.getMessage()); }
        check(SceneLibrary.find(dir, "../x") == null && SceneLibrary.find(dir, "") == null && SceneLibrary.find(dir, "nope.rj") == null, "find() refuses odd or missing names");
        SceneLibrary.delete(SceneLibrary.find(dir, "Foo.rj"));
        check(SceneLibrary.find(dir, "Foo.rj") == null, "delete removes the scene");
        check(SceneLibrary.folderName("a/b:c").equals("a_b_c.rj") && SceneLibrary.folderName("").equals("scene.rj") && SceneLibrary.folderName(".hid.zip").equals("scene_hid.rj"), "folderName cleans: " + SceneLibrary.folderName("a/b:c") + ", " + SceneLibrary.folderName(""));
        System.out.println(fails == 0 ? "ALL PASSED" : fails + " FAILED"); System.exit(fails == 0 ? 0 : 1);
    }
}
