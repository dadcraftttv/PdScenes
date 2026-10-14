// SPDX-License-Identifier: GPL-3.0-or-later
package app.pdscenes;

import android.content.ContentResolver;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;

/**
 * Imports scenes from a folder the user picked in the system file picker. The folder can be one
 * scene ("Eargasm.rj") or a folder of scenes ("rjdj_scenes"); every scene found is copied into
 * the library.
 */
final class TreeImporter {

    /** What happened to a folder import. */
    static final class Result {
        final List<SceneLibrary.Scene> imported = new ArrayList<>();
        final List<String> failed = new ArrayList<>();
    }

    private static final int MAX_DEPTH = 2;   // picked folder, a folder of scenes, one more level

    private static final class Doc {
        final String id;
        final String name;
        final boolean isDir;

        Doc(String id, String name, boolean isDir) {
            this.id = id;
            this.name = name;
            this.isDir = isDir;
        }
    }

    private final ContentResolver resolver;
    private final Uri tree;
    private final File scenesDir;

    private TreeImporter(ContentResolver resolver, Uri tree, File scenesDir) {
        this.resolver = resolver;
        this.tree = tree;
        this.scenesDir = scenesDir;
    }

    static Result importTree(ContentResolver resolver, Uri tree, File scenesDir) {
        TreeImporter importer = new TreeImporter(resolver, tree, scenesDir);
        Result result = new Result();
        String rootId = DocumentsContract.getTreeDocumentId(tree);
        importer.visit(new Doc(rootId, importer.nameOf(rootId), true), 0, result);
        return result;
    }

    /** Copies the whole picked folder into {@code dest} (a stem pack: the caller finds pack.txt in it). */
    static void copyAll(ContentResolver resolver, Uri tree, File dest) throws IOException {
        if (!dest.mkdirs()) {
            throw new IOException("Cannot create " + dest);
        }
        TreeImporter importer = new TreeImporter(resolver, tree, dest);
        importer.copyInto(DocumentsContract.getTreeDocumentId(tree), dest);
    }

    /** The picked folder's own name. */
    static String treeName(ContentResolver resolver, Uri tree) {
        return new TreeImporter(resolver, tree, null).nameOf(DocumentsContract.getTreeDocumentId(tree));
    }

    /** Copies {@code dir} as a scene if it holds _main.pd; otherwise looks in its sub-folders. */
    private void visit(Doc dir, int depth, Result result) {
        List<Doc> children = children(dir.id);
        boolean isScene = false;
        for (Doc c : children) {
            if (!c.isDir && c.name.equals(SceneLibrary.MAIN_PATCH)) {
                isScene = true;
                break;
            }
        }
        if (isScene) {
            copyScene(dir, result);
        } else if (depth < MAX_DEPTH) {
            for (Doc c : children) {
                if (c.isDir && !c.name.startsWith(".")) {
                    visit(c, depth + 1, result);
                }
            }
        }
    }

    private void copyScene(Doc dir, Result result) {
        File staging = SceneLibrary.newStaging(scenesDir);
        try {
            if (!staging.mkdirs()) {
                throw new IOException("Cannot create " + staging);
            }
            copyInto(dir.id, staging);
            result.imported.add(SceneLibrary.installFolder(staging, dir.name, scenesDir));
        } catch (IOException | RuntimeException e) {
            result.failed.add(dir.name);
        } finally {
            SceneLibrary.deleteRecursively(staging);
        }
    }

    private void copyInto(String dirId, File dest) throws IOException {
        for (Doc c : children(dirId)) {
            if (c.name.startsWith(".")) {
                continue;   // hidden files and Mac metadata
            }
            File out = new File(dest, c.name);
            if (c.isDir) {
                if (!out.mkdirs()) {
                    throw new IOException("Cannot create " + out);
                }
                copyInto(c.id, out);
            } else {
                Uri uri = DocumentsContract.buildDocumentUriUsingTree(tree, c.id);
                try (InputStream in = resolver.openInputStream(uri);
                     OutputStream os = new FileOutputStream(out)) {
                    if (in == null) {
                        throw new IOException("Cannot read " + c.name);
                    }
                    byte[] buf = new byte[32 * 1024];
                    int n;
                    while ((n = in.read(buf)) > 0) {
                        os.write(buf, 0, n);
                    }
                }
            }
        }
    }

    private List<Doc> children(String parentId) {
        List<Doc> result = new ArrayList<>();
        Uri uri = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parentId);
        String[] cols = {DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE};
        try (Cursor c = resolver.query(uri, cols, null, null, null)) {
            while (c != null && c.moveToNext()) {
                boolean isDir = DocumentsContract.Document.MIME_TYPE_DIR.equals(c.getString(2));
                result.add(new Doc(c.getString(0), c.getString(1), isDir));
            }
        }
        return result;
    }

    private String nameOf(String docId) {
        Uri uri = DocumentsContract.buildDocumentUriUsingTree(tree, docId);
        try (Cursor c = resolver.query(uri,
                new String[]{DocumentsContract.Document.COLUMN_DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst()) {
                return c.getString(0);
            }
        }
        return "scene";
    }
}
