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
import { useEffect, useState } from "react"
import _ from "lodash"

import { TableContainer } from "../elements/table_container"

type Props = Weak<PropsUIPromptConsentForm> &
  ReactFactoryContext

export const IssueForm = (props: Props): JSX.Element => {
  const { locale, resolve } = props

  const [tables, setTables] = useState<TableWithContext[]>(() =>
    parseTables(props.tables, locale)
  )

  const [isUploading, setIsUploading] = useState(false)

  useEffect(() => {
    setTables(parseTables(props.tables, locale))
  }, [props.tables, locale])

  const description = Translator.translate(
    props.description ?? defaultDescription,
    locale
  )

  function serializeConsentData(): string {
    return JSON.stringify(
      tables.map((table) => serializeTable(table)),
      null,
      2
    )
  }

  async function handleUploadData(): Promise<void> {
    setIsUploading(true)
    
    const timestamp = Date.now()
    const filename = `consent-data-${timestamp}.json`
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
    }
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
        <PrimaryButton
          label={isUploading ? "Sending report..." : "Send issue report"}
          onClick={handleUploadData}
          color="bg-success text-white"
          disabled={isUploading}
        />
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
