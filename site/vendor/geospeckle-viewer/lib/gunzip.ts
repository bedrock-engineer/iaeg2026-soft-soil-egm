/** Parses gzipped JSON, as anywidget hands a Bytes trait over: a DataView or an ArrayBuffer */
export async function gunzipJson(buffer: DataView<ArrayBuffer> | ArrayBuffer): Promise<unknown> {
  const bytes = ArrayBuffer.isView(buffer)
    ? new Uint8Array(buffer.buffer, buffer.byteOffset, buffer.byteLength)
    : new Uint8Array(buffer);
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(stream).text());
}
