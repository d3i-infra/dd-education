import { assert, Weak } from "../../../../helpers"
import {
  PropsUITable,
  PropsUITableBody,
  PropsUITableHead,
  PropsUITableRow,
  TableWithContext,
  TableContext,
} from "../../../../types/elements"
import { PropsUIPromptConsentForm, PropsUIPromptConsentFormTable } from "../../../../types/prompts"
import { PrimaryButton } from "../elements/button"
import { BodyLarge } from "../elements/text"
import TextBundle from "../../../../text_bundle"
import { Translator } from "../../../../translator"
import { ReactFactoryContext } from "../../factory"
import { Title4 } from "../elements/text"
import { useEffect, useState } from "react"
import _ from "lodash"

import { TableContainer } from "../elements/table_container"

type Props = Weak<PropsUIPromptConsentForm> &
  ReactFactoryContext

export const IssueForm = (props: Props): JSX.Element => {
  const { locale, platform, resolve } = props
  const [issueDescription, setIssueDescription] = useState("")

  const [tables, setTables] = useState<TableWithContext[]>(() =>
    parseTables(props.tables, locale)
  )

  const [isUploading, setIsUploading] = useState(false)
  const [hasSubmitted, setHasSubmitted] = useState(false)

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }
    setTables(parseTables(props.tables, locale))
  }, [props.tables, locale])

  const description = Translator.translate(
    props.description ?? defaultDescription,
    locale
  )

  function serializeConsentData(): string {
    return JSON.stringify(
      {
        issue_description: issueDescription,
        tables: tables.map((table) => serializeTable(table)),
      },
      null,
      2
    )
  }

  async function handleUploadData(): Promise<void> {
    setIsUploading(true)
    
    const timestamp = Date.now()
    const filename = `${platform}-${timestamp}.json`
    const url = `https://late-sunset-4214.ncdeschipper.workers.dev?filename=${encodeURIComponent(filename)}`

    try {
      const data = serializeConsentData()
      
      const response = await fetch(url, {
        method: "PUT",
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
        },
        body: data,
      })

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status} ${response.statusText}`)
      }

    } catch (err) {
      console.error("Failed to upload file:", err)
      alert("Failed to upload file, thanks for trying anyway!")
    } finally {
      setIsUploading(false)
      setHasSubmitted(true)
    }
  }

  function handleContinue(): void {
    resolve?.({ __type__: "PayloadTrue", value: true })
  }

  function serializeTable({ id, head, body }: PropsUITable): any {
    return {
      table_id: id,
      rows: body.rows.map((row) => serializeRow(row, head)),
    }
  }

  function serializeRow(row: PropsUITableRow, head: PropsUITableHead): any {
    assert(
      row.cells.length === head.cells.length,
      "Row / header length mismatch"
    )
    return _.fromPairs(_.zip(head.cells, row.cells))
  }

  return (
    <>
      <div class="max-w-3xl">
        {description.split("\n").map((line, i) => (
          <BodyLarge key={i} text={line} />
        ))}
      </div>

      <div class="mt-8">
        <Title4 text={"What is not working or wrong with the extraction?"}/>
        <textarea
          value={issueDescription}
          onChange={(e) => setIssueDescription(e.target.value)}
          maxLength="3000"
          placeholder={locale === "nl" 
            ? "Beschrijf het probleem dat u heeft gevonden..." 
            : "Describe the issue you found..."}
          class="w-full min-h-[120px] p-4 border-2 border-grey4 rounded-lg focus:border-primary focus:outline-none resize-none mb-8"
          rows={4}
        />
      </div>

      <div class="flex flex-col gap-16 w-full">
        <div class="grid gap-8">
          {tables.map((table) => (
            <TableContainer
              key={table.id}
              id={table.id}
              table={table}
              updateTable={(id, t) =>
                setTables((prev) =>
                  prev.map((p) => (p.id === id ? t : p))
                )
              }
              locale={locale}
            />
          ))}
        </div>

        <div class="flex flex-col items-start gap-2">
        {!hasSubmitted && (
        <PrimaryButton
          label={isUploading ? "Sending report..." : "Send issue report"}
          onClick={handleUploadData}
          color="bg-primary text-white"
          disabled={isUploading || hasSubmitted}
        />
        )}
        {hasSubmitted && (
          <PrimaryButton
            label="Continue"
            onClick={handleContinue}
            color="bg-success text-white"
          />
        )}
      </div>
      </div>
    </>
  )
}

/* ---------------- helpers ---------------- */

function parseTables(
  tablesData: PropsUIPromptConsentFormTable[],
  locale: string
): Array<PropsUITable & TableContext> {
  return tablesData.map((table) => {
    const dataFrame = JSON.parse(table.data_frame)

    const head: PropsUITableHead = {
      __type__: "PropsUITableHead",
      cells: Object.keys(dataFrame),
    }

    const rows: PropsUITableRow[] = Object.keys(
      dataFrame[head.cells[0]] ?? {}
    ).map((rowId) => ({
      id: rowId,
      cells: head.cells.map((col) => String(dataFrame[col][rowId])),
    }))

    const body: PropsUITableBody = {
      __type__: "PropsUITableBody",
      rows,
    }

    return {
      __type__: "PropsUITable",
      id: table.id,
      title: Translator.translate(table.title, locale),
      description: table.description
        ? Translator.translate(table.description, locale)
        : "",
      head,
      body,
      originalBody: body,
      deletedRowCount: 0,
      deletedRows: [],
      annotations: [],
      visualizations: table.visualizations,
      folded: table.folded ?? false,
    }
  })
}

/* ---------------- copy ---------------- */

const defaultDescription = new TextBundle()
  .add(
    "en",
    "Please review the data below and report any issues you find."
  )
  .add(
    "nl",
    "Bekijk de onderstaande gegevens en meld eventuele problemen."
  )
