import { useState } from "react"
import { ReactFactoryContext, Translator } from "@eyra/feldspar"
import { PropsUIPromptIssueForm } from "./types"

type Props = PropsUIPromptIssueForm & ReactFactoryContext

const UPLOAD_URL = "https://late-sunset-4214.ncdeschipper.workers.dev"

/** Convert column-oriented DataFrame JSON to array of row objects. */
function dataFrameToRows(
  data_frame: any
): { columns: string[]; rows: Record<string, string>[] } {
  try {
    const df = typeof data_frame === "string" ? JSON.parse(data_frame) : data_frame
    if (df && typeof df === "object" && !Array.isArray(df)) {
      // Column-oriented: {"col": {"0": val, "1": val, ...}}
      const columns = Object.keys(df)
      if (columns.length === 0) return { columns: [], rows: [] }
      const indices = Object.keys(df[columns[0]] || {})
      const rows = indices.map((idx) =>
        Object.fromEntries(
          columns.map((col) => [col, String(df[col]?.[idx] ?? "")])
        )
      )
      return { columns, rows }
    }
  } catch {
    /* ignore parse errors */
  }
  return { columns: [], rows: [] }
}

export function IssueForm({ description, tables, platform, locale, resolve }: Props) {
  const [issueDescription, setIssueDescription] = useState("")
  const [isUploading, setIsUploading] = useState(false)
  const [hasSubmitted, setHasSubmitted] = useState(false)

  function serializeData(): string {
    const serializedTables = tables.map((table) => {
      const { rows } = dataFrameToRows(table.data_frame)
      return {
        id: table.id,
        title: Translator.translate(table.title as any, locale),
        data: rows,
      }
    })
    return JSON.stringify({
      issueDescription,
      tables: serializedTables,
    })
  }

  async function handleUpload() {
    setIsUploading(true)
    try {
      const timestamp = new Date().toISOString().replace(/[:.]/g, "-")
      const filename = `${platform}-${timestamp}.json`
      const response = await fetch(`${UPLOAD_URL}/${filename}`, {
        method: "PUT",
        headers: { "Content-Type": "text/plain" },
        body: serializeData(),
      })
      if (!response.ok) {
        alert("Upload failed. Please try again later.")
      }
    } catch (error) {
      alert("Upload failed. Please try again later.")
    } finally {
      setIsUploading(false)
      setHasSubmitted(true)
    }
  }

  function handleContinue() {
    resolve?.({ __type__: "PayloadFalse", value: false })
  }

  const descriptionText = Translator.translate(description as any, locale)

  return (
    <div className="flex flex-col gap-6">
      {descriptionText.split("\n\n").map((paragraph, i) => (
        <p key={i} className="text-grey2">{paragraph}</p>
      ))}

      <div>
        <label className="text-title6 font-title6">
          {locale === "nl"
            ? "Wat werkt er niet of wat klopt er niet aan de extractie?"
            : "What is not working or wrong with the extraction?"}
        </label>
        <textarea
          className="w-full mt-2 p-3 border rounded min-h-[120px]"
          maxLength={3000}
          value={issueDescription}
          onChange={(e) => setIssueDescription(e.target.value)}
        />
      </div>

      {tables.map((table) => {
        const { columns, rows } = dataFrameToRows(table.data_frame)

        return (
          <div key={table.id} className="mb-4">
            <h3 className="text-title6 font-title6 mb-2">
              {Translator.translate(table.title as any, locale)}
            </h3>
            {table.description && (
              <p className="text-grey2 mb-2">
                {Translator.translate(table.description as any, locale)}
              </p>
            )}
            {columns.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr>
                      {columns.map((col) => (
                        <th key={col} className="border p-2 bg-grey6 text-left">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.slice(0, 50).map((row, i) => (
                      <tr key={i}>
                        {columns.map((col) => (
                          <td key={col} className="border p-2">{row[col]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )
      })}

      <div className="flex gap-4">
        <button
          className="btn bg-primary text-white px-6 py-2 rounded disabled:opacity-50"
          onClick={handleUpload}
          disabled={isUploading || hasSubmitted}
        >
          {isUploading
            ? (locale === "nl" ? "Verzenden..." : "Sending...")
            : (locale === "nl" ? "Stuur probleemrapport" : "Send issue report")}
        </button>
        {hasSubmitted && (
          <button
            className="btn bg-grey5 px-6 py-2 rounded"
            onClick={handleContinue}
          >
            {locale === "nl" ? "Doorgaan" : "Continue"}
          </button>
        )}
      </div>
    </div>
  )
}
