const PIPE_CODE_SCHEMA =
  (typeof globalThis !== "undefined" && globalThis.PIPE_CODE_DEFINITION) || null;

if (!PIPE_CODE_SCHEMA) {
  throw new Error("PIPE_CODE_DEFINITION is not loaded.");
}

const { pattern, labels, enums } = PIPE_CODE_SCHEMA;

function cleanText(value) {
  return String(value ?? "").trim().toUpperCase();
}

function normalizeDigits(value, width = 0) {
  const digits = String(value ?? "").replace(/[^\d]/g, "");
  if (!digits) {
    return "";
  }
  const normalized = String(Number.parseInt(digits, 10));
  return width ? normalized.padStart(width, "0") : normalized;
}

function enumMeta(group, value, customLabel) {
  if (!value) {
    return null;
  }

  const label = group[value];
  if (label) {
    return { code: value, label, isCustom: false };
  }

  return { code: value, label: customLabel || value, isCustom: true };
}

function validateField(key, value) {
  if (!value || !pattern[key]) {
    return true;
  }
  return pattern[key].test(value);
}

function normalizeSegments(input = {}) {
  const materialCode = cleanText(input.materialCode);
  const unitNo = normalizeDigits(input.unitNo, 2);
  const lineSeq = normalizeDigits(input.lineSeq, 2);
  const pipeSize = normalizeDigits(input.pipeSize);
  const pressureGradeCode = cleanText(input.pressureGradeCode);
  const classSequenceNo = normalizeDigits(input.classSequenceNo);
  const materialCategoryCode = cleanText(input.materialCategoryCode);
  const insulationThickness = normalizeDigits(input.insulationThickness);
  const insulationType = cleanText(input.insulationType);

  return {
    materialCode,
    unitNo,
    lineSeq,
    pipeSize,
    pressureGradeCode,
    classSequenceNo,
    materialCategoryCode,
    insulationThickness,
    insulationType,
    unitAndSeq: unitNo && lineSeq ? `${unitNo}${lineSeq}` : "",
    pipeClass:
      pressureGradeCode && classSequenceNo && materialCategoryCode
        ? `${pressureGradeCode}${classSequenceNo}${materialCategoryCode}`
        : "",
    insulationCode:
      insulationThickness && insulationType ? `${insulationThickness}${insulationType}` : "",
  };
}

function compose(input = {}) {
  const segments = normalizeSegments(input);
  const requiredKeys = [
    "materialCode",
    "unitNo",
    "lineSeq",
    "pipeSize",
    "pressureGradeCode",
    "classSequenceNo",
    "materialCategoryCode",
    "insulationThickness",
    "insulationType",
  ];

  if (requiredKeys.some((key) => !segments[key])) {
    return "";
  }

  return [
    segments.materialCode,
    segments.unitAndSeq,
    segments.pipeSize,
    segments.pipeClass,
    segments.insulationCode,
  ].join("-");
}

function parse(rawCode = "") {
  const normalizedRaw = cleanText(rawCode).replace(/\s+/g, "");
  const result = {
    ok: false,
    raw: rawCode ?? "",
    normalized: "",
    segments: {},
    display: {},
    errors: [],
    warnings: [],
  };

  const parts = normalizedRaw.split("-").filter(Boolean);
  if (parts.length !== 5) {
    result.errors.push("编号结构应为 5 段：物料-主项编号管道序号-管径-管道等级-绝热隔声代号。");
    return result;
  }

  const [materialCode, unitAndSeq, pipeSize, pipeClass, insulationCode] = parts;
  const pipeClassMatch = pipeClass.match(/^([A-Z])(\d+)([A-Z])$/);
  const insulationCodeMatch = insulationCode.match(/^(\d+)([A-Z])$/);

  if (!pattern.materialCode.test(materialCode)) {
    result.errors.push(`${labels.materialCode}格式不合法: ${materialCode}`);
  }

  if (!/^\d{4}$/.test(unitAndSeq)) {
    result.errors.push("主项编号+管道序号格式不合法: " + unitAndSeq);
  }

  if (!pattern.pipeSize.test(pipeSize)) {
    result.errors.push(`${labels.pipeSize}格式不合法: ${pipeSize}`);
  }

  if (!pipeClassMatch) {
    result.errors.push(`${labels.pipeClass}格式不合法: ${pipeClass}`);
  }

  if (!insulationCodeMatch) {
    result.errors.push(`${labels.insulationCode}格式不合法: ${insulationCode}`);
  }

  const segments = {
    materialCode,
    unitNo: unitAndSeq.slice(0, 2),
    lineSeq: unitAndSeq.slice(2, 4),
    pipeSize,
    pressureGradeCode: pipeClassMatch ? pipeClassMatch[1] : "",
    classSequenceNo: pipeClassMatch ? pipeClassMatch[2] : "",
    materialCategoryCode: pipeClassMatch ? pipeClassMatch[3] : "",
    insulationThickness: insulationCodeMatch ? insulationCodeMatch[1] : "",
    insulationType: insulationCodeMatch ? insulationCodeMatch[2] : "",
  };

  result.segments = normalizeSegments(segments);

  [
    "materialCode",
    "unitNo",
    "lineSeq",
    "pipeSize",
    "pressureGradeCode",
    "classSequenceNo",
    "materialCategoryCode",
    "insulationThickness",
    "insulationType",
    "pipeClass",
    "insulationCode",
  ].forEach((key) => {
    if (result.segments[key] && !validateField(key, result.segments[key])) {
      result.errors.push(`${labels[key]}格式不合法: ${result.segments[key]}`);
    }
  });

  result.display = explain(result.segments);

  if (result.display.materialCode?.isCustom) {
    result.warnings.push(`materialCode 使用了未收录枚举值 ${result.segments.materialCode}。`);
  }
  if (result.display.pressureGradeCode?.isCustom) {
    result.warnings.push(`pressureGradeCode 使用了未收录枚举值 ${result.segments.pressureGradeCode}。`);
  }
  if (result.display.materialCategoryCode?.isCustom) {
    result.warnings.push(
      `materialCategoryCode 使用了未收录枚举值 ${result.segments.materialCategoryCode}。`,
    );
  }
  if (result.display.insulationType?.isCustom) {
    result.warnings.push(`insulationType 使用了未收录枚举值 ${result.segments.insulationType}。`);
  }

  result.normalized = compose(result.segments);
  result.ok = result.errors.length === 0 && Boolean(result.normalized);
  return result;
}

function explain(input) {
  const segments = input.pipeClass ? input : normalizeSegments(input);
  return {
    materialCode: enumMeta(
      enums.materialCodes,
      segments.materialCode,
      "项目补充物料代号（待确认）",
    ),
    pressureGradeCode: enumMeta(enums.pressureGradeCodes, segments.pressureGradeCode),
    classSequenceNo: segments.classSequenceNo
      ? {
          code: segments.classSequenceNo,
          label: `材料等级顺序号 ${segments.classSequenceNo}`,
          isCustom: false,
        }
      : null,
    materialCategoryCode: enumMeta(
      enums.materialCategoryCodes,
      segments.materialCategoryCode,
    ),
    insulationType: enumMeta(enums.insulationTypeCodes, segments.insulationType),
  };
}

const PIPE_CODE_PARSER = {
  compose,
  parse,
  explain,
};

if (typeof globalThis !== "undefined") {
  globalThis.PIPE_CODE_PARSER = PIPE_CODE_PARSER;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = PIPE_CODE_PARSER;
}
