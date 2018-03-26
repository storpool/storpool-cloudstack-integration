/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
package org.apache.cloudstack.storage.datastore.util;

import java.io.PrintWriter;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.UnsupportedEncodingException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.apache.http.HttpResponse;
import org.apache.http.client.ClientProtocolException;
import org.apache.http.client.methods.HttpRequestBase;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.ContentType;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.DefaultHttpClient;
//import org.apache.http.impl.conn.BasicClientConnectionManager;

import org.apache.log4j.Logger;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonParser;
import com.google.gson.JsonObject;

import com.cloud.utils.exception.CloudRuntimeException;
import com.cloud.utils.script.OutputInterpreter;
import com.cloud.utils.script.Script;


public class StorpoolUtil {
    private static final Logger log = Logger.getLogger(StorpoolUtil.class);


    private static PrintWriter spLogFile = spLogFileInitialize();

    private static PrintWriter spLogFileInitialize() {
        try {
            log.info("INITIALIZE SP-LOG_FILE");
            return new PrintWriter("/var/log/cloudstack/management/storpool-plugin.log");
        } catch (Exception e) {
            log.info("INITIALIZE SP-LOG_FILE: " + e.getMessage());
            throw new RuntimeException(e);
        }
    }

    public static void spLog(String fmt, Object... args) {
        final String line = String.format(fmt, args);
        spLogFile.println(line);
        spLogFile.flush();
    }


    public static final String SP_PROVIDER_NAME = "StorPool";
    public static final String SP_DEV_PATH = "/dev/storpool/";

    public static enum StorpoolRights {
        RO("ro"),
        RW("rw"),
        DETACH("detach");

        private final String name;

        private StorpoolRights(String name) {
            this.name = name;
        }

        public String toString() {
            return name;
        }
    }

    public static final class SpApiError {
        private String name;
        private String descr;

        public SpApiError() {}

        public String getName() {
            return this.name;
        }

        public String getDescr() {
            return this.descr;
        }

        public void setName(String name) {
            this.name = name;
        }

        public void setDescr(String descr) {
            this.descr = descr;
        }

        public String toString() {
            return String.format("%s: %s", name, descr);
        }
    }

    public static class SpApiResponse {
        private SpApiError error;
        public JsonElement fullJson;

        public SpApiResponse() {}

        public SpApiError getError() {
            return this.error;
        }

        public void setError(SpApiError error)
        {
            this.error = error;
        }
    }

    public static String devPath(final String name) {
        return String.format("%s%s", SP_DEV_PATH, name);
    }

    public static int getStorpoolId(final String hostName) {
        Script sc = new Script("/usr/lib/storpool/confget", 0, log);
        sc.add("-f", "/etc/storpool.conf");
        sc.add("-s", hostName);
        sc.add("SP_OURID");

        OutputInterpreter.OneLineParser parser = new OutputInterpreter.OneLineParser();

        final String err = sc.execute(parser);
        if (err != null) {
            final String errMsg = String.format("Could not extract SP_OURID for host %s. Error: %s", hostName, err);
            log.warn(errMsg);
            throw new CloudRuntimeException(errMsg);
        }

        return Integer.parseInt(parser.getLine());
    }

//    private static void spError(final String fmt, Object... args) {
//        final String msg = String.format(fmt, args);
//        throw new CloudRuntimeException(msg);
//    }

    private static SpApiResponse spApiRequest(HttpRequestBase req, String query) {
        String SP_API_HOST = null;
        String SP_API_PORT = null;
        String SP_AUTH_TOKEN = null;

        Script sc = new Script("storpool_confget", 0, log);
        OutputInterpreter.AllLinesParser parser = new OutputInterpreter.AllLinesParser();

        final String err = sc.execute(parser);
        if (err != null) {
            final String errMsg = String.format("Could not execute storpool_confget. Error: %s", err);
            log.warn(errMsg);
            throw new CloudRuntimeException(errMsg);
        }

        for (String line: parser.getLines().split("\n")) {
            String[] toks = line.split("=");
            if( toks.length != 2 ) {
                log.debug("unexpected line in storpool_confget output: " + line);
                continue;
            }

            switch (toks[0]) {
                case "SP_API_HTTP_HOST":
                    SP_API_HOST = toks[1];
                    break;

                case "SP_API_HTTP_PORT":
                    SP_API_PORT = toks[1];
                    break;

                case "SP_AUTH_TOKEN":
                    SP_AUTH_TOKEN = toks[1];
                    break;
            }
        }

        if (SP_API_HOST == null) {
            throw new CloudRuntimeException("Invalid StorPool config. Missing SP_API_HTTP_HOST");
        }

        if (SP_API_PORT == null) {
            throw new CloudRuntimeException("Invalid StorPool config. Missing SP_API_HTTP_PORT");
        }

        if (SP_AUTH_TOKEN == null) {
            throw new CloudRuntimeException("Invalid StorPool config. Missing SP_AUTH_TOKEN");
        }


        try (DefaultHttpClient httpClient = new DefaultHttpClient()) {
            final String qry = String.format("http://%s:%s/ctrl/1.0/%s", SP_API_HOST, SP_API_PORT, query);
            final URI uri = new URI(qry);

            req.setURI(uri);
            req.addHeader("Authorization", String.format("Storpool v1:%s", SP_AUTH_TOKEN));

            final HttpResponse resp = httpClient.execute(req);
//            Storpool error message is returned in response body, so try and extract it
//            final int respCode = resp.getStatusLine().getStatusCode();
//            if (respCode != 200) {
//                spError("Failed to execute %s. StorPool API requrned error code %d", qry, respCode);
//            }

            Gson gson = new Gson();
            BufferedReader br = new BufferedReader(new InputStreamReader(resp.getEntity().getContent()));

            JsonElement el = new JsonParser().parse(br);

            SpApiResponse apiResp = gson.fromJson(el, SpApiResponse.class);
            apiResp.fullJson = el;
            return apiResp;
        } catch (UnsupportedEncodingException ex) {
            throw new CloudRuntimeException(ex.getMessage());
        } catch (ClientProtocolException ex) {
            throw new CloudRuntimeException(ex.getMessage());
        } catch (IOException ex) {
            throw new CloudRuntimeException(ex.getMessage());
        } catch (URISyntaxException ex) {
            throw new CloudRuntimeException(ex.getMessage());
        }
    }

    private static SpApiResponse GET(String query) {
        return spApiRequest(new HttpGet(), query);
    }

    private static SpApiResponse POST(String query, Object json) {
        HttpPost req = new HttpPost();
        if (json != null) {
            Gson gson = new Gson();
            String js = gson.toJson(json);
            StringEntity input = new StringEntity(js, ContentType.APPLICATION_JSON);
            req.setEntity(input);
        }

        return spApiRequest(req, query);
    }


    public static boolean templateExists(final String name) {
        SpApiResponse resp = GET("VolumeTemplateDescribe/" + name);
        return resp.getError() == null;
    }

    public static boolean volumeExists(final String name) {
        SpApiResponse resp = GET("Volume/" + name);
        return resp.getError() == null;
    }

    public static boolean snapshotExists(final String name) {
        SpApiResponse resp = GET("Snapshot/" + name);
        return resp.getError() == null;
    }

    public static long snapshotSize( final String name ) {
        SpApiResponse resp = GET("Snapshot/" + name);
        JsonObject obj = resp.fullJson.getAsJsonObject();

        JsonObject data = obj.getAsJsonArray("data").get(0).getAsJsonObject();
        return data.getAsJsonPrimitive("size").getAsLong();
    }

    public static SpApiResponse volumeCreate(final String name, final String parentName, final String template, final Long size) {
        Map<String, Object> json = new HashMap<>();
        json.put("name", name);
        json.put("parent", parentName);
        json.put("template", template);
        json.put("size", size);

        return POST("VolumeCreate", json);
    }

    public static SpApiResponse volumeUpdate(final String name, final Long newSize, final Boolean shrinkOk) {
        Map<String, Object> json = new HashMap<>();
        json.put("size", newSize);
        json.put("shrinkOk", shrinkOk);

        return POST("VolumeUpdate/" + name, json);
    }

    public static SpApiResponse volumeSnapshot(final String volumeName, final String snapshotName) {
        Map<String, Object> json = new HashMap<>();
        json.put("name", snapshotName);

        return POST("VolumeSnapshot/" + volumeName, json);
    }

    public static SpApiResponse volumeFreeze(final String volumeName) {
        return POST("VolumeFreeze/" + volumeName, null);
    }

    public static SpApiResponse volumeDelete(final String name) {
        detachAllForced(name, false);
        return POST("VolumeDelete/" + name, null);
    }

    public static SpApiResponse snapshotDelete(final String name) {
        detachAllForced(name, true);
        return POST("SnapshotDelete/" + name, null);
    }

/*
    public static SpApiResponse volumeReassign(final String name, final boolean snapshot, final int clientId, final StorpoolRights rights) {
        if (snapshot && rights == StorpoolRights.RW) {
            throw new IllegalArgumentException("Storpool snapshots can only be attached read-only");
        }

        List<Map<String, Object>> json = new ArrayList<>();
        Map<String, Object> reassignDesc = new HashMap<>();
        reassignDesc.put(snapshot ? "snapshot" : "volume", name);
        int[] clients = { clientId };
        reassignDesc.put(rights.toString(), clients);
        json.add(reassignDesc);

        return POST("VolumesReassign", json);
    }
*/
    private static void detachAllForced(final String name, final boolean snapshot) {
        final String type = snapshot ? "snapshot" : "volume";
        List<Map<String, Object>> json = new ArrayList<>();
        Map<String, Object> reassignDesc = new HashMap<>();
        reassignDesc.put(type, name);
        reassignDesc.put("detach", "all");
        reassignDesc.put("force", true);
        json.add(reassignDesc);

        final SpApiResponse resp = POST("VolumesReassign", json);
        if (resp.getError() != null) {
            final String err = String.format("Force detach failed for %s %s. Error: %s", type, name, resp.getError());
            spLog(err);
//            throw new CloudRuntimeException(err);
        }
    }
}
