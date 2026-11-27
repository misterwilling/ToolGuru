import type { LengthUnit, SimilarGroup, SimilarMember, SimilarView } from '../types'
import { formatDuration, groupSummary, variantCells, variantHeadings } from '../utils'

/** Cutters side by side: what differs between them, and how much each was used. */
export function VariantTable({
  differs,
  members,
  display,
}: {
  differs: string[]
  members: SimilarMember[]
  display: LengthUnit
}) {
  return (
    <div className="scroll">
      <table className="plain">
        <thead>
          <tr>
            <th>Description</th>
            {variantHeadings(differs, display).map((heading) => (
              <th key={heading} className="num">{heading}</th>
            ))}
            <th className="num" title="Programs that used it">PGMs</th>
            <th className="num" title="Operations that used it">OPs</th>
            <th className="num">Cutting time</th>
          </tr>
        </thead>
        <tbody>
          {members.map((member) => (
            <tr key={member.cutter_key}>
              <td>
                {member.description || '—'}
                {member.merged && <span className="tag">already merged</span>}
              </td>
              {variantCells(member, members[0], differs, display).map((cell, index) => (
                <td key={index} className="num">
                  {cell.differs ? <span className="differs">{cell.text}</span> : cell.text}
                </td>
              ))}
              <td className="num">{member.programs}</td>
              <td className="num">{member.operations}</td>
              <td className="num">{formatDuration(member.time_s)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface Props {
  similar: SimilarView
  display: LengthUnit
  disabled: boolean
  run: (action: string, data?: unknown) => Promise<void>
}

/** Cutters that are probably one tool entered more than one way, to be merged or left apart. */
export function SimilarScreen({ similar, display, disabled, run }: Props) {
  const keys = (group: SimilarGroup) => group.members.map((member) => member.cutter_key)
  return (
    <section className="detail">
      <div className="actions">
        <button disabled={disabled} onClick={() => run('close_similar')}>‹ Back to the tally</button>
      </div>

      <h3>
        Similar cutters{' '}
        <span className="note">
          — the same type, diameter, flutes and corner radius. The first line of each is the most used; what differs
          from it is marked.
        </span>
      </h3>
      {similar.suggestions.length === 0 && <p className="muted">Nothing to decide.</p>}
      {similar.suggestions.map((group) => (
        <div className="panel" key={group.signature}>
          <div className="panel-head">
            <b>{groupSummary(group)}</b>
            <span className="actions">
              <button
                className="primary"
                disabled={disabled}
                onClick={() => run('merge_cutters', { cutterKeys: keys(group) })}
              >
                Treat as same
              </button>
              <button disabled={disabled} onClick={() => run('not_similar', { signature: group.signature })}>
                Not the same
              </button>
            </span>
          </div>
          <VariantTable differs={group.differs} members={group.members} display={display} />
        </div>
      ))}

      <h3 className="after">
        Treated as same <span className="note">— counted as one tool in the tally. Split to count them apart again.</span>
      </h3>
      {similar.merged.length === 0 && <p className="muted">None yet.</p>}
      {similar.merged.map((group) => (
        <div className="panel" key={group.cutter_key}>
          <div className="panel-head">
            <b>{groupSummary(group)}</b>
            <button disabled={disabled} onClick={() => run('split_cutters', { cutterKey: group.cutter_key })}>
              Split
            </button>
          </div>
          <VariantTable differs={group.differs} members={group.members} display={display} />
        </div>
      ))}
    </section>
  )
}
