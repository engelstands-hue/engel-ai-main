export function ConnectionField() {
  return (
    <div className="connection-field" aria-hidden="true">
      <div className="connection-field__orbit connection-field__orbit--outer" />
      <div className="connection-field__orbit connection-field__orbit--inner" />
      <span className="connection-field__node connection-field__node--a" />
      <span className="connection-field__node connection-field__node--b" />
      <span className="connection-field__node connection-field__node--c" />
      <span className="connection-field__node connection-field__node--d" />
      <div className="connection-field__core">
        <span className="connection-field__spark" />
        <strong>Human</strong>
        <small>in control</small>
      </div>
    </div>
  );
}
