// Built-in example: a branching tree. Sensors are integer arrival times
// generated from a leak on segment b-c with a small inconsistency so the
// optimum residual is nonzero (shows both witnesses and half-integer data).
export const sampleDraft = () => ({
  edges: [
    { id: "P1", from: "N0", to: "N1", length: 8 },
    { id: "P2", from: "N1", to: "N2", length: 6 },
    { id: "P3", from: "N1", to: "N3", length: 4 },
    { id: "P4", from: "N2", to: "N4", length: 3 },
    { id: "P5", from: "N2", to: "N5", length: 5 },
  ],
  sensors: [
    { id: "S1", node: "N0", arrival: 10 },
    { id: "S2", node: "N3", arrival: 14 },
    { id: "S3", node: "N4", arrival: 11 },
    { id: "S4", node: "N5", arrival: 13 },
  ],
});

export const emptyDraft = () => ({ edges: [], sensors: [] });
